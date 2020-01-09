from nla_control.models import *
from django.db.models import Sum

def run():
    # get the files with status ONTAPE
    files = TapeFile.objects.filter(stage=TapeFile.ONTAPE)
    print("Number of files on tape: " + str((len(files))))
    print("Total size             : " + str(files.aggregate(Sum('size'))))
