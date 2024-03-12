
from django.test import TestCase
import os

# Create your tests here.

from models import Quota


class SimpleTest(TestCase):

    def setUp(self):
        self.object_list = []
        q = Quota(user="_TEST", size=100000000)
        q.save()
        self.object_list.append(q)

    def tearDown(self):
        for item in self.object_list:
            item.delete()

    def test_up(self):
        resp = self.client.get('/nla_control/quota/_TEST/requests')
        self.assertEqual(resp.status_code, 200)


#Add to primary tape archive
#Initiate daily?
#for each file on disk in filesets marked for archive on tape:
#   if the file is verifiable in the storage-d system and
#           has an older modified date than the verification time
#   then: add the file to the primary tape archive
#            make a file request with a retention to 20 days against a system user quota.
#            signpost info it left in directory structure.

#Delete from disk
#Initiate hourly? {can the user initiate this process}
#For each file request where the retention is past:
#   check that the file has not been modified since retention.
#   if not modified then delete and remove request.

#Make a request
#On user request
#Input file patterns and retention date.
#expand user request to list of files
#for each file make a file request with new flagged and retention time set.

#retrieve a batch of files
#Initiated on user request or cron? {Need some fair share queuing - managing the q is separate from managing the individual requests}
#for each new requested file submit retrieve request, set retrieving flag.
#for each request with retrieving set: see if files have arrived: {Is there already a notifying thing for storage-d?}
#   if so set to flag as arrived.
#   if notification set then send email

#List requests
#On user request
#input file patterns and optional valid date.
#expand user requested files patterns to a list of file request where valid date < retention date
#print list of files with retention times, retrieval state and sizes
#print total sizes

#List tape files
#On user request
#Input file patterns.
#Expand user requested files patterns to a list of tape files.
#Print list of tape files.

#Alter file request retention time
#On user request
#Input file patterns and retention date.
#Expand user requested files patterns to list of file requests.
#Set list of file requests to new retention time.

#Add a notification
#On user request
#input file pattern and email address.
#make a notification
#Expand user requested files patterns to list of file requests.
#set the notification on the set of file requests.
#Move data back to disk as primary storage

#Look at tape files
#compare with fileset marked for archive on tape.
#If files no longer on to be on tape then:
#initiate a retrive for files.
#remove request (to stop deletion)
#once on disk remove tape file entry.

#Adds or changes quota.
#Admin goes to web interface and changes quotas.


