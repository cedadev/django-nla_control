NLA User Guide
==============

Some times we keep data on tape only. This is used for very voluminous datasets, for example, Sentinel data.

Accessing the tape archive from JASMIN.
---------------------------------------

Request a tape quota by emailing the CEDA help desk.

Download the command line interface from https://github.com/cedadev/nla_client.git

``git clone https://github.com/cedadev/nla_client.git``

First run the client by running 

``python nla.py``

You can type "help" to get a list of help topics / commands.  Type help <command> to get help using a particular command.

The first thing to do determine the names of the files in the NLA that you want to restore.  You use the “ls” command to do this, which can also take a substring to search for, e.g. “ls sentinel1a”

There are two ways to make a request:

1.       Listing request.  Here you supply a list of file names to restore in a file.  E.g. “listing_request request_1.txt”. (you can supply any path to the listing file, here it’s in the same directory as nla.py, which is probably not how you would be invoking it)

2.       Pattern request.  Here you supply a substring that must appear in the filename.  E.g. “pattern_request 2015” will recover all files with “2015” in the filename.  This particular request (2015) is not recommend as it will restore a lot of files!  Something more specific like “S2A_OPER_PRD_MSIL1C_PDMC_20161007” would be better

You can view your requests by invoking “requests” (and see how much of your quota you have used)

You can view the details of a request by “req request-number”

You can check which files are in a request by “requested_files request-number”

Requests have a retention date.  After this date the restored files will be removed.  You can extend this retention date by using “retain request-number yyyy-mm-dd”

You can expire a request early using “expire request-number”.  This will remove your restored files within 24 hours and free up some of your quota.

You can label a request by using “label label-name”.  The default label name is either the first file in a listing_request or the pattern in a pattern_request.

You can be informed via email when your files are ready using the “notify” command.  The system knows your email address so simply doing “notify” will inform you when the first files arrive and the last files arrive.  To notify someone else use “notify email-address”.  To notify different people when the first and last arrive use “notify_first email-address” and “notify_last” email-address.

You can check your quota via “quota”


