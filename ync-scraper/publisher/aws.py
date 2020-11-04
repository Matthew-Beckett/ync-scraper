import boto3
import os
import logging

class Publisher():
    def __init__(self, client):
        self.client = boto3.client(client)

class SmsPublisher(Publisher):
    def __init__(self, sns_topic_arn: str, logger):
        super().__init__('sns')
        self.sns_topic_arn = sns_topic_arn
        self.logger = logger
    
    def publish(self, subject: str, message: str):
        if os.environ.get('YNC_DEBUG_MODE'):
            self.logger.info(message)
        else:
            self.logger.info(message)
            response = self.client.publish(
                TopicArn=self.sns_topic_arn,Subject=subject, 
                Message=message,
                MessageAttributes = {
                    'AWS.SNS.SMS.SMSType': {
                        'DataType': 'String',
                        'StringValue': 'Promotional'
                        }
                    }
                )

class EmailPublisher(Publisher):
    def __init__(self, sender: str, recipient: str, logger, char_set = "UTF-8"):
        super().__init__('ses')
        self.logger = logger
        self.sender = sender
        self.char_set = char_set
        self.recipient = recipient
    
    def publish(self, subject: str, message: str):
        if os.environ.get('YNC_DEBUG_MODE'):
            self.logger.info(message)
        else:
            self.logger.info(message)
            response = self.client.send_email(
                Destination={
                    'ToAddresses': [
                        self.recipient,
                    ],
                },
                Message={
                    'Body': {
                        'Text': {
                            'Charset': self.char_set,
                            'Data': message,
                        },
                    },
                    'Subject': {
                        'Charset': self.char_set,
                        'Data': subject,
                    },
                },
                Source=self.sender
            )
            self.logger.info(f"Email sent! Message ID:{response['MessageId']}")
