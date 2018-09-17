# Create your views here.
from django.http import HttpResponse
from nla_control.models import *
from django.shortcuts import redirect, render_to_response, get_object_or_404
import json
import datetime
from django.views.generic import View

class RequestView(View):
    """:rest-api

    Requests to resources which put (PUT) a request for file retrieval from tape into the NLA system,
    get (GET) information about a single request and modify (POST) a single request.
    """

    def get(self, request, *args, **kwargs):
        """:rest-api

        .. http:get:: /nla_control/api/v1/requests/req_id

            Get information about a single request.

            :param integer req_id: (*optional*) unique id for the request

            ..

            :>jsonarr integer id: unique id of the request
            :>jsonarr string quota: the user id for the quota to use in making the request
            :>jsonarr DateTime retention: date when restored files will be removed from restore area
            :>jsonarr DateTime request_date: date when a request was made
            :>jsonarr string request_patterns: pattern to match against to retrieve files from tape
            :>jsonarr string notify_on_first_file: email address to notify when first restored file is available in the restore area
            :>jsonarr string notify_on_last_file: email address to notify when last file is available in restore area - i.e. the request is complete
            :>jsonarr string label: a user defined label for the request
            :>jsonarr string storaged_request_start: (*optional*) the date and time the retrieval request started on StorageD
            :>jsonarr string storaged_request_end: (*optional*) the date and time the retrieval request concluded on StorageD
            :>jsonarr string first_files_on_disk: (*optional*) the date and time the first files arrived on the restore disk
            :>jsonarr string last_files_on_disk: (*optional*) the date and time the last files arrived on the restore disk
            :>jsonarr List[string] files: list of files in the request

            :statuscode 200: request completed successfully
            :statuscode 404: request with `req_id` not found

            ..

            **Example request**

            .. sourcecode:: http

                GET /nla_control/api/v1/requests/225 HTTP/1.1
                Host: nla.ceda.ac.uk
                Accept: application/json

            ..

            **Example response**

            .. sourcecode:: http

                HTTP/1.1 200 OK
                Vary: Accept
                Content-Type: application/json

                [
                  {
                    "files": [
                               "/neodc/sentinel1a/data/IW/L1_GRD/h/IPF_v2/2016/02/23/S1A_IW_GRDH_1SSV_20160223T132730_20160223T132755_010074_00ED60_3761.zip"
                             ],
                    "request_date": "2017-02-08T14:00:56.786661",
                    "first_files_on_disk": "2017-02-08T14:01:49.652354",
                    "quota": "dhk63261",
                    "storaged_request_start": "2017-02-08T14:01:28.614195",
                    "request_patterns": "/neodc/sentinel1a/data/IW/L1_GRD/h/IPF_v2/2016/02/23/S1A_IW_GRDH_1SSV_20160223T132730_20160223T132755_010074_00ED60_3761",
                    "notify_on_last_file": null,
                    "id": 225,
                    "retention": "2017-03-10T00:00:00",
                    "last_files_on_disk": "2017-02-08T14:01:49.679483",
                    "notify_on_first_file": null,
                    "label": "/neodc/sentinel1a/data/IW/L1_GRD/h/IPF_v2/2016/02/23/S1A_IW_GRDH_1SSV_20160223T132730_20160223T132755_010074_00ED60_3761",
                    "storaged_request_end": "2017-02-08T14:01:49.679476"
                  }
                ]

        .. http:get:: /nla_control/api/v1/requests

            Get a list of all requests which have not passed their retention date.

            ..

            :>jsonarr List[Dictionary] requests: list of all requests submitted to the NLA system.  Each dictionary contains:

            ..

               - **id** (*integer*): the id of the request
               - **quota** (*string*): the user who made the request
               - **retention** (*DateTime*): the date and time the request will expire on
               - **request_date** (*DateTime*): the date and time the request was made
               - **label** (*string*): the label assigned to the request by the user, or a default of the request pattern or first file in a listing request

            :statuscode 200: request completed successfully

            ..

            **Example request**

            .. sourcecode:: http

                GET /nla_control/api/v1/requests HTTP/1.1
                Host: nla.ceda.ac.uk
                Accept: application/json

            ..

            **Example response**

            .. sourcecode:: http

                HTTP/1.1 200 OK
                Vary: Accept
                Content-Type: application/json

                [
                  {
                    "requests": [
                                  {
                                    "label": "/neodc/sentinel1a/data/IW/L1_SLC/IPF_v2/2016/12/30/S1A_IW_SLC__1SDV_20161230T153351_20161230T153418_014611_017C04_9E83.zip",
                                    "retention": "2017-03-29T00:00:00",
                                    "id": 257,
                                    "request_date": "2017-02-27T12:58:02.398858",
                                    "quota": "jweiss"
                                  },
                                  {
                                    "label": "/neodc/sentinel1a/data/IW/L1_SLC/IPF_v2/2015/04/16/S1A_IW_SLC__1SSV_20150416T135155_20150416T135225_005510_007092_F761.zip",
                                    "retention": "2017-03-29T00:00:00",
                                    "id": 262,
                                    "request_date": "2017-02-27T18:42:42.313259",
                                    "quota": "dcm39"
                                  },
                                  {
                                    "label": "FTEP and UK",
                                    "retention": "2019-01-01T00:00:00",
                                    "id": 129,
                                    "request_date": "2016-12-02T12:15:35.975215",
                                    "quota": "ewilliamson01"
                                  }
                                ]
                  }
                ]

        """
        # return details of a single request
        if "req_id" in kwargs:
            req = get_object_or_404(TapeRequest, pk=kwargs["req_id"])
            data = {"id": req.pk, "quota": req.quota.user, "retention": req.retention.isoformat(),
                    "request_date": req.request_date.isoformat(),
                    "request_patterns": req.request_patterns,
                    "notify_on_first_file": req.notify_on_first_file,
                    "notify_on_last_file": req.notify_on_last_file,
                    "label": req.label
                    }
            if req.storaged_request_start:
                data["storaged_request_start"] = req.storaged_request_start.isoformat()
            if req.storaged_request_end:
                data["storaged_request_end"] = req.storaged_request_end.isoformat()
            if req.first_files_on_disk:
                data["first_files_on_disk"] = req.first_files_on_disk.isoformat()
            if req.last_files_on_disk:
                data["last_files_on_disk"] = req.last_files_on_disk.isoformat()
            files = []
            if len(req.files.all()) != 0:
                for f in req.files.all():
                    files.append(f.logical_path)
            elif req.request_files:
                for f in req.request_files.split():
                    files.append(f)
            elif req.request_patterns:
                patt_files = TapeFile.objects.filter(logical_path__contains=req.request_patterns)
                for f in patt_files:
                    files.append(f.logical_path)

            data["files"] = files
            return HttpResponse(json.dumps(data), content_type="application/json")

        # list all requests if no request specified
        else:
            requests = []
            for req in TapeRequest.objects.all():
                req_data = {"id": req.pk, "quota": req.quota.user, "retention": req.retention.isoformat(),
                        "request_date": req.request_date.isoformat(),
                        "label": req.label}
                requests.append(req_data)
            data = {"requests": requests}
            return HttpResponse(json.dumps(data), content_type="application/json")

    def check_quota(self, data):
        # get user quota
        user = data['quota']
        quota = Quota.objects.filter(user=user)
        if len(quota) != 1:
            return False, quota, ("No quota for user %s" % user)

        quota = quota[0]

        # before making the request check whether requesting the files would go
        # over the user's quota - get the total size of the request first

        total_size = 0

        # two methods of calculating this depending on type of request
        # 1. if files are specified then add up the files
        # 2. if a pattern is specified then add up the files that currently match the pattern

        if "request_files" in data:
            file_reqs = TapeFile.objects.filter(logical_path__in=data["request_files"].split())
        elif "patterns" in data:
            file_reqs = TapeFile.objects.filter(logical_path__contains=data["patterns"])

        # can now add up the file_requests
        for f in file_reqs:
            total_size += f.size

        # check whether this and previously requested files are greater than the user's quota
        if quota.used(datetime.datetime.now()) + total_size > quota.size:
            return False, quota, "Requested file(s) exceed user's quota"

        return True, quota, ""


    def post(self, request, *args, **kwargs):
        """:rest-api

        .. http:post:: /nla_control/api/v1/requests

            Make a request to restore a file from tape.

            ..

            :<jsonarr string quota: the user id for the quota to use in making the request
            :<jsonarr string patterns: (*optional*) pattern to match against to retrieve files from tape
            :<jsonarr string files: (*optional*) list of files to retrieve from tape
            :<jsonarr DateTime retention: (*optional*) date when restored files will be removed from restore area.  Default is 5 days from when the request was made.
            :<jsonarr string label: (*optional*) a user defined label for the request
            :<jsonarr string notify_on_first_file: (*optional*) email address to notify when first restored file is available in the restore area
            :<jsonarr string notify_on_last_file: (*optional*) email address to notify when last file is available in restore area - i.e. the request is complete

            :>json integer req_id: success, the unique identifier of the request
            :>json string error_msg: error, a message detailing the error is returned

            :statuscode 200: request completed successfully
            :statuscode 403: error with user quota: either the user quota is full or the user could not be found

            **Example request**

            .. sourcecode:: http

                POST /nla_control/api/v1/requests HTTP/1.1
                Host: nla.ceda.ac.uk
                Accept: application/json
                Content-Type: application/json

                [
                  {
                    "patterns": "1986",
                    "quota": "dhk63261",
                    "retention": "2017-04-01"
                  }
                ]


            **Example response**

            .. sourcecode:: http

                HTTP/1.1 200 OK
                Vary: Accept
                Content-Type: application/json

                [
                  {
                    "req_id": 23
                  }
                ]

                [
                  {
                    "error": "Requested file(s) exceed user's quota"
                  }
                ]

        """
        data = request.read()
        data = json.loads(data)

        # set pattern
        if "patterns" in data:
            original_patterns = data["patterns"]
            data["request_files"] = ""
        else:
            original_patterns = ""

        # set retention date
        if "retention" in data:
            retention = datetime.datetime.strptime(data['retention'], "%Y-%m-%d")
        else:
            retention = datetime.datetime.now() + datetime.timedelta(days=5)

        # set files
        if "files" in data:
            original_patterns = ""
            # build the request files list as a string (delimited by \n)
            data["request_files"] = ""
            for d in data["files"]:
                data["request_files"] += d + "\n"

        # check the quota
        quota_pass, quota, error_msg = self.check_quota(data)
        if not quota_pass:
            return HttpResponse(json.dumps({"error": error_msg}),
                                content_type="application/json",
                                status=403,
                                reason=error_msg)

        # create the tape request then set data
        req = TapeRequest(retention=retention, quota=quota, request_patterns=original_patterns)

        # set notifications, etc
        # if not label then set the label to be the pattern of the request (first 2024 characters)
        if "label" in data:
            req.label = data["label"]
        else:
            if "files" in data:
                req.label = data["files"][0]
            else:
                req.label = original_patterns

        # if request does not have a notify_on_first_file then set the notify to be the
        # quota owner's email address
        if "notify_on_first_file" in data:
            if data["notify_on_first_file"]:    # check if it is not the null string
                req.notify_on_first_file = data["notify_on_first_file"]
            else:
                req.notify_on_first_file = quota.email_address

        # if request does not have a notify_on_last_file then set the notify to be the
        # quota owner's email address
        if "notify_on_last_file" in data:
            if data["notify_on_last_file"]:  # check if it is not the null string
                req.notify_on_last_file = data["notify_on_last_file"]
            else:
                req.notify_on_first_file = quota.email_address

        # save the requested files
        req.request_files = data["request_files"]
        req.save()

        return HttpResponse(json.dumps({"req_id": req.pk}), content_type="application/json")

    def put(self, request, *args, **kwargs):
        """:rest-api

        .. http:put:: /nla_control/api/v1/requests/req_id

            Update a request to restore a file from tape.

            :param integer req_id: unique id of request to update

            ..

            :<jsonarr string quota: the user id for the quota to use in making the request
            :<jsonarr DateTime retention: (*optional*) date when restored files will be removed from restore area.  Default is 5 days from when the request was made.
            :<jsonarr string label: (*optional*) a user defined label for the request
            :<jsonarr string notify_on_first_file: (*optional*) email address to notify when first restored file is available in the restore area
            :<jsonarr string notify_on_last_file: (*optional*) email address to notify when last file is available in restore area - i.e. the request is complete

            :statuscode 200: request completed successfully
            :statuscode 403: user id could not be found: they have no associated quota
            :statuscode 404: request with `req_id` could not be found


            **Example request**

            .. sourcecode:: http

                PUT /nla_control/api/v1/requests/23 HTTP/1.1
                Host: nla.ceda.ac.uk
                Accept: application/json
                Content-Type: application/json

                [
                  {
                    "label": "Test request for 1986 data",
                    "quota": "dhk63261",
                    "retention": "2017-04-01",
                    "notify_on_first_file": "neil.massey@stfc.ac.uk"
                  }
                ]


            **Example response**

            .. sourcecode:: http

                HTTP/1.1 200 OK
                Vary: Accept
                Content-Type: application/json

                [
                  {
                    "req_id": 23
                  }
                ]

                [
                  {
                    "error": "No quota for user dhk8934"
                  }
                ]
        """
        req = get_object_or_404(TapeRequest, pk=kwargs["req_id"])
        data = request.read()
        data = json.loads(data)
        # get the quota so that we can get the user's email address
        quota= Quota.objects.filter(user=data["quota"])
        if len(quota) != 1:
            error_msg = "No quota for user %s" % user
            return HttpResponse(json.dumps({"error": (error_msg)}),
                                content_type="application/json",
                                status=403,
                                reason=error_msg)
        quota = quota[0]

        # set notifications, etc
        if "label" in data:
            req.label = data["label"]
        if "retention" in data:
            req.retention = data["retention"]
        if "notify_on_first_file" in data:
            if data["notify_on_first_file"]:    # check if it is not the null string
                req.notify_on_first_file = data["notify_on_first_file"]
            else:                               # if null string then use email from quota
                req.notify_on_first_file = quota.email_address
        if "notify_on_last_file" in data:
            if data["notify_on_last_file"]:
                req.notify_on_last_file = data["notify_on_last_file"]
            else:
                req.notify_on_last_file = quota.email_address
        req.save()

        return HttpResponse(json.dumps({"req_id": req.pk}), content_type="application/json")


class QuotaView(View):
    """:rest-api

    Requests to resources which return information about a users Quota in the NLA system
    """

    def get(self, request, *args, **kwargs):
        """:rest-api

        .. http:get:: /nla_control/api/v1/quota/id

            Get information about the user, specifically their quota, request and user details.

            :param string id: unique id for the user - currently the same as their JASMIN user-id

            ..

            :>jsonarr integer id: numeric id for the user
            :>jsonarr string user: user name (as on JASMIN) for the user, the same as the quota name
            :>jsonarr integer size: quota size in bytes
            :>jsonarr integer used: amount used from quota, in bytes
            :>jsonarr string email: email address of the user
            :>jsonarr string notes: any notes on the user (project associated with, etc.)
            :>jsonarr List[Dictionary] requests: list of requests submitted by the user.  Each dictionary contains:

            ..

                - **id** (`integer`): the id of the request
                - **request_date** (`DateTime`): the date and time the request was made
                - **retention** (`DateTime`): the date and time the request will expire on
                - **label** (`string`): the label assigned to the request by the user, or a default of the request pattern or first file in a listing request
                - **storaged_request_start** (`DateTime`): (*optional*) the date and time the retrieval request started on StorageD
                - **storaged_request_end** (`DateTime`): (*optional*) the date and time the retrieval request concluded on StorageD
                - **first_files_on_disk** (`DateTime`): (*optional*) the date and time the first files arrived on the restore disk
                - **last_files_on_disk** (`DateTime`): (*optional*) the date and time the last files arrived on the restore disk

            :statuscode 200: request completed successfully.
            :statuscode 404: user with `id` not found.

            **Example request**

            .. sourcecode:: http

                GET /nla_control/api/v1/quota/dhk63261 HTTP/1.1
                Host: nla.ceda.ac.uk
                Accept: application/json

            **Example response**

            .. sourcecode:: http

                HTTP/1.1 200 OK
                Vary: Accept
                Content-Type: application/json

                [
                  {
                    "used": 1981562009,
                    "notes": "Test user account for Neil Massey",
                    "id": 6,
                    "user": "dhk63261",
                    "requests": [
                                  {
                                    "last_files_on_disk": "2017-02-08T14:01:49.679483",
                                    "request_date": "2017-02-08T14:00:56.786661",
                                    "first_files_on_disk": "2017-02-08T14:01:49.652354",
                                    "label": "/neodc/sentinel1a/data/IW/L1_GRD/h/IPF_v2/2016/02/23/S1A_IW_GRDH_1SSV_20160223T132730_20160223T132755_010074_00ED60_3761",
                                    "storaged_request_start": "2017-02-08T14:01:28.614195",
                                    "storaged_request_end": "2017-02-08T14:01:49.679476",
                                    "id": 225,
                                    "retention": "2017-03-10T00:00:00"
                                  },
                                  {
                                    "last_files_on_disk": "2017-02-06T12:16:29.912293",
                                    "request_date": "2017-02-06T11:02:17.498464",
                                    "first_files_on_disk": "2017-02-06T12:15:21.549330",
                                    "label": "/neodc/sentinel2a/data/L1C_MSI/2016/10/07/S2A_OPER_PRD_MSIL1C_PDMC_20161007T232231_R040_V20161007T162332_20161007T163154.zip",
                                    "storaged_request_start": "2017-02-06T11:57:49.437537",
                                    "storaged_request_end": "2017-02-06T12:16:29.912284",
                                    "id": 212,
                                    "retention": "2017-03-30T00:00:00"
                                  }
                                ],
                    "email": "neil.massey@stfc.ac.uk",
                    "size": 1099511627776
                  }
                ]

        """
        # return details of a single request
        quota = get_object_or_404(Quota, user=kwargs["user"])
        data = {"id": quota.pk, "user": quota.user, "size": quota.size,
                "email": quota.email_address, "notes": quota.notes,
                "used": quota.used(datetime.datetime.now())}

        requests = []
        for req in quota.requests():
            req_data = {"id": req.pk, "retention": req.retention.isoformat(),
                    "request_date": req.request_date.isoformat(),
                    "label": req.label}
            if req.storaged_request_start:
                req_data["storaged_request_start"] = req.storaged_request_start.isoformat()
            if req.storaged_request_end:
                req_data["storaged_request_end"] = req.storaged_request_end.isoformat()
            if req.first_files_on_disk:
                req_data["first_files_on_disk"] = req.first_files_on_disk.isoformat()
            if req.last_files_on_disk:
                req_data["last_files_on_disk"] = req.last_files_on_disk.isoformat()

            requests.append(req_data)

        data["requests"] = requests

        return HttpResponse(json.dumps(data), content_type="application/json")


class TapeFileView(View):
    """:rest-api

    Requests to resources which return information about the TapeFiles in the NLA system.
    """

    def get(self, request, *args, **kwargs):
        """:rest-api

        .. http:get:: /nla_control/api/v1/files

            Get a list of TapeFiles, optionally matching by a substring and by the stage of the file.

            :queryparam string match: (*optional*) Substring to match against in the name of the TapeFile.

            :queryparam string stages: (*optional*) String containing any combination of **UDTAR**, to match only
                those files at a particular stage in the NLA system:

            ..

                - **U**: UNVERIFIED
                - **D**: ONDISK
                - **T**: ONTAPE
                - **A**: RESTORING
                - **R**: RESTORED

            :queryparam string spot-name: (*optional*) String containing `true`|`false`.  If `true` then will return the name of the spot in the JSON.

            :>jsonarr integer count: Number of files matching request.
            :>jsonarr List[Dictionary] files: Details of the files returned, each dictionary contains:

            ..

                - **path** (`string`): logical path to the file.
                - **spot-name** (`string`): name of the spot where the file was originally held.
                - **stage** (`char`): current stage of the file, one of **UDTAR** as above.
                - **verified** (`DateTime`): the date and time the file was verified on.
                - **size** (`integer`): the size of the file in bytes.

            :statuscode 200: request completed successfully.

            **Example request**

            .. sourcecode:: http

                GET /nla_control/api/v1/files?match=L1C_MSI/2016/09/05&stages=R HTTP/1.1
                Host: nla.ceda.ac.uk
                Accept: application/json

            **Example response**

            .. sourcecode:: http

                HTTP/1.1 200 OK
                Vary: Accept
                Content-Type: application/json

                [
                  {
                    "count": 3,
                    "files": [
                               {
                                 "path": "/neodc/sentinel2a/data/L1C_MSI/2016/09/05/S2A_OPER_PRD_MSIL1C_PDMC_20160907T072856_R008_V20160905T104022_20160905T104021.zip",
                                 "stage": "R",
                                 "verified": "2017-01-18T16:59:05.244150",
                                 "size": 7781712577
                               },
                               {
                                 "path": "/neodc/sentinel2a/data/L1C_MSI/2016/09/05/S2A_OPER_PRD_MSIL1C_PDMC_20160907T074525_R008_V20160905T104022_20160905T104021.zip",
                                 "stage": "R",
                                 "verified": "2017-01-18T16:59:05.244150",
                                 "size": 7184875123
                               },
                               {
                                 "path": "/neodc/sentinel2a/data/L1C_MSI/2016/09/05/S2A_OPER_PRD_MSIL1C_PDMC_20160907T061411_R008_V20160905T104022_20160905T104021.zip",
                                 "stage": "R",
                                 "verified": "2017-01-18T16:59:05.244150",
                                 "size": 8545489398
                               }
                            ]
                  }
                ]

        """

        # return details for files
        match = request.GET.get("match", "")
        stages = request.GET.get("stages", "UDTAR")
        spot = request.GET.get("spot", "false")

        stage_map = {"U": TapeFile.UNVERIFIED, "D": TapeFile.ONDISK, "T": TapeFile.ONTAPE,
                     "A": TapeFile.RESTORING, "R": TapeFile.RESTORED,}
        inverse_stage_map = {v: k for k, v in stage_map.items()}

        stage_list = []
        for s in stages:
            if s in stage_map:
                stage_list.append(stage_map[s])


        # load tape file mappings if spot is true
        if spot.lower() == "true":
            opener = urllib2.build_opener()

            page = opener.open(CEDA_DOWNLOAD_CONF)
            fileset_logical_path_map = {}

            # make a dictionary that maps logical paths to spot names
            for line in page:
                line = line.strip()
                if line == '':
                    continue
                spot_name, logical_path = line.split()
                fileset_logical_path_map[logical_path] = spot_name

        tfiles = TapeFile.objects.filter(logical_path__contains=match, stage__in=stage_list)

        data = {"count": len(tfiles)}
        filelist = []
        for f in tfiles:
            if f.verified:
                verified = f.verified.isoformat()
            else:
                verified = None
            if spot.lower() == "true":
                lpath = f.logical_path
                for i in range(0,3):
                    # get the directory name
                    head, tail = os.path.split(lpath)
                    if head in fileset_logical_path_map:
                        spot_name = fileset_logical_path_map[head]
                        break
                    lpath = head
                filelist.append({"path": f.logical_path, "spot-name": spot_name, "size": f.size,
                                 "verified": verified, "stage": inverse_stage_map[f.stage]})
            else:
                filelist.append({"path": f.logical_path, "size": f.size,
                                 "verified": verified, "stage": inverse_stage_map[f.stage]})
        data["files"] = filelist

        return HttpResponse(json.dumps(data), content_type="application/json")


def unverified_spots(request):
    """Get a list of unverified spots, in a similar manner as the "get" method above but just returning a 
       text file that can be more easily processed"""
    # get a list of unverified files
    unv_files = TapeFile.objects.filter(stage=TapeFile.UNVERIFIED)

    # build a mapping of filenames to spots
    opener = urllib2.build_opener()

    page = opener.open(CEDA_DOWNLOAD_CONF)
    fileset_logical_path_map = {}

    # make a dictionary that maps logical paths to spot names
    for line in page:
        line = line.strip()
        if line == '':
            continue
        spot_name, logical_path = line.split()
        fileset_logical_path_map[logical_path] = spot_name

    # we only want one instance per spot so create a set to store the spots
    spotlist = set()

    # loop over the files
    for f in unv_files:
        lpath = f.logical_path
        for i in range(0,3):
            # get the directory name
            head, tail = os.path.split(lpath)
            if head in fileset_logical_path_map:
                spotlist.add(fileset_logical_path_map[head])
                break
            lpath = head
    # create the text
    spotlist_text = ""
    for s in spotlist:
        spotlist_text += s + "\n"

    return HttpResponse(spotlist_text, content_type="text/plain")
