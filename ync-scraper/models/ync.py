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