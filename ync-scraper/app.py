import requests
import base64
import boto3
import re
import os
import sys
import logging

from bs4 import BeautifulSoup
from pprint import pprint, pformat
from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute, ListAttribute, NumberAttribute

class YncListing(Model):
    class Meta:
        table_name = "ync-database"
        region = "eu-west-1"
    VehicleId = NumberAttribute(hash_key=True)
    _VehicleId = NumberAttribute()
    VehicleTitle = UnicodeAttribute()
    VehicleDescription = UnicodeAttribute()
    VehiclePriceNumber = NumberAttribute()
    VehicleFeatures = ListAttribute()
    VehicleMileage = UnicodeAttribute()
    DetectedVehicleNumberplate = UnicodeAttribute()
    ListingLink = UnicodeAttribute()

BASE_URL = "https://www.yournextcarltd.co.uk"
SEARCH_URL = "https://www.yournextcarltd.co.uk/search_page.php?budgetswitch=0&vehicle_type=car&sort=l&make=8&model=&body=&gearbox=automatic&doors=&body_colour=&fuel_type=&seats=&yearmin=2016&yearmax=2018&budgetmin=&budgetmax=25000"
RESULT_CLASS_NAME = "container vehicle results-prestige youtube veh-loc-1"
AI_READY_NUMBERPLATE_REGEX = '(^[A-Z]{2}[A-Z0-9]{2}\s?[A-Z]{3}$)|(^[A-Z][0-9]{1,3}[A-Z]{3}$)|(^[A-Z]{3}[0-9]{1,3}[A-Z]$)|(^[0-9]{1,4}[A-Z]{1,2}$)|(^[0-9]{1,3}[A-Z]{1,3}$)|(^[A-Z]{1,2}[0-9]{1,4}$)|(^[A-Z]{1,3}[0-9]{1,3}$)|(^[A-Z]{1,3}[0-9]{1,4}$)|(^[0-9]{3}[DX]{1}[0-9]{3}$)'
SNS_TOPIC_ARN = 'arn:aws:sns:eu-west-1:466873411642:YNCTextNotifications'

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

def convert_price_to_int(price):
    parsed_price = price.replace('£', '')
    parsed_price = parsed_price.replace(' ', '')
    parsed_price = parsed_price.replace(',', '')
    return int(parsed_price)

def publish_new_car_notification(database_item: YncListing):
    client = boto3.client('sns')
    message = f"""
        A new car has been listed on YNC!
        {database_item.VehicleTitle}
        {database_item.VehicleDescription}
        Mileage: {database_item.VehicleMileage}
        Price: £{database_item.VehiclePriceNumber}
        {database_item.ListingLink}
        """
    if os.environ.get('YNC_DEBUG_MODE'):
        logger.info(message)
    else:
        logger.info(message)
        client.publish(
            TopicArn=SNS_TOPIC_ARN,Subject="Car listed on YNC has changed in price", 
            Message=message,
            MessageAttributes = {
                'AWS.SNS.SMS.SMSType': {
                    'DataType': 'String',
                    'StringValue': 'Promotional'
                    }
                }
            )

def publish_price_change_notification(database_item: YncListing, old_price, new_price):
    client = boto3.client('sns')
    message = f"""
        A car listed on YNC has changed in price!
        {database_item.VehicleTitle}
        Old Price: £{old_price}
        New Price: £{new_price}
        {database_item.ListingLink}
        """
    if os.environ.get('YNC_DEBUG_MODE'):
        logger.info(message)
    else:
        logger.info(message)
        client.publish(
            TopicArn=SNS_TOPIC_ARN,Subject="Car listed on YNC has changed in price", 
            Message=message,
            MessageAttributes = {
                'AWS.SNS.SMS.SMSType': {
                    'DataType': 'String',
                    'StringValue': 'Promotional'
                    }
                }
            )

def publish_vehicle_sold_notification(database_item: YncListing):
    client = boto3.client('sns')
    message = f"""
        A car listed on YNC has been sold! :(
        {database_item.VehicleTitle}
        """
    if os.environ.get('YNC_DEBUG_MODE'):
        logger.info(message)
    else:
        logger.info(message)
        client.publish(
            TopicArn=SNS_TOPIC_ARN,Subject="Car listed on YNC has been sold", 
            Message=message,
            MessageAttributes = {
                'AWS.SNS.SMS.SMSType': {
                    'DataType': 'String',
                    'StringValue': 'Promotional'
                    }
                }
            )

def lambda_handler(event, context):
    results = requests.get(SEARCH_URL)
    parsed_results = BeautifulSoup(results.content, 'html.parser')
    count_of_pages = int((((parsed_results.find(class_='pagenavi').find(class_='next')['href']).split('&'))[-1]).replace('p=', ''))
    cars = list()
    page_counter = 0
    while page_counter != count_of_pages:
        page_counter += 1
        paginated_url = f'{SEARCH_URL}&p={page_counter}'
        results = requests.get(paginated_url)
        for listing in parsed_results.find_all(class_=RESULT_CLASS_NAME):
            cars.append(listing)

    active_listings = list()

    for car in cars:
        vehicle_title_section = car.find(class_="eightcol vehicle-title")
        vehicle_title = vehicle_title_section.find('h3').find('a').text

        vehicle_page_suffix = vehicle_title_section.find('h3').find('a').get('href')
        vehicle_id = (vehicle_page_suffix.split('-'))[-1]
        logger.info(f"Working on car {vehicle_title} with id {vehicle_id}")
        active_listings.append(vehicle_id)
        
        try:
            database_item = YncListing.get(int(vehicle_id))
            database_item.VehicleId = database_item._VehicleId
            vehicle_price = convert_price_to_int(car.find(class_='price-is').next)
            if vehicle_price != database_item.VehiclePriceNumber:
                publish_price_change_notification(database_item, database_item.VehiclePriceNumber,vehicle_price)
                database_item.VehiclePriceNumber = vehicle_price
                database_item.save()

        except YncListing.DoesNotExist:
            database_item = YncListing(int(vehicle_id))
            database_item._VehicleId = int(vehicle_id)

            vehicle_price = car.find(class_='price-is').next
            vehicle_mileage = car.find(class_='icon-mileage').next
            
            features = list()
            feature_list = car.find_all(class_='icon-checkmark')
            for feature in feature_list:
                features.append(str(feature.next))
            
            vehicle_description = features[0] #Capture vehicle descrption
            features.remove(features[0]) #Remove vehicle description from feature list
            features.remove(features[-1]) #Remove sales bullshit in last item
            
            vehicle_first_image_url = car.find(class_='fourcol').find('img').get('data-src')
            vehicle_first_image = base64.b64encode(requests.get(vehicle_first_image_url).content)
            vehicle_first_image_binary = base64.decodebytes(vehicle_first_image)
            recognition_client = boto3.client('rekognition')
            response = recognition_client.detect_text(
                Image={
                    "Bytes" : vehicle_first_image_binary
                }
            )
            detected_text = newlist = sorted(response['TextDetections'], key=lambda k: k['Confidence'])
            for index, detection in enumerate(detected_text):
                detected_text[index] = detection['DetectedText']
            search_expression = re.compile(AI_READY_NUMBERPLATE_REGEX)
            potential_numberplates = list(filter(search_expression.match, detected_text))
            if len(potential_numberplates) < 1:
                likeliest_numberplate = "DETECTION_FAILED"
            else:
                likeliest_numberplate = max(potential_numberplates, key=len)
            
            database_item.DetectedVehicleNumberplate = str(likeliest_numberplate)  
            database_item.VehicleTitle = str(vehicle_title)
            database_item.VehicleDescription = str(vehicle_description)
            database_item.VehicleMileage = str(vehicle_mileage)
            database_item.VehiclePriceNumber = int(convert_price_to_int(vehicle_price))
            database_item.VehicleFeatures = list(features)
            database_item.ListingLink = str(f'{BASE_URL}{vehicle_page_suffix}')
            publish_new_car_notification(database_item)
        
            database_item.save()

    for active_listing in active_listings:
        database_item = YncListing.get(int(active_listing))
        if database_item._VehicleId:
            continue
        else:
            log.info(f'Deleting car {database_item.VehicleId}')
            database_item.delete()

lambda_handler("", "")