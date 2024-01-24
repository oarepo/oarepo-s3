Invenio - Direct multipart upload to S3 server
===

On CESNET, we have an object storage based on CEPH clusters with radosgw interface, which is an Amazon S3 compatible REST API service. It will be abbreviated below as "s3.cesnet.cz".

See [proposed REST API](#Proposed-REST-API) if you just want to see the proposal.

REST API of oarepo-s3 (OLD implementation)
---

### Multipart initiation
```
POST /draft/records/<id>/files/?multipart=True
payload:
{
  "key": ""
}

response:
{
   "key": "same as above",
   "uploadId": "generated upload id for subsequent calls",
}
```

*Note:* we do not specify the number of parts here as S3 does not need it at this moment.

### Getting presigned urls for uploading parts
```
GET /draft/records/<id>/files/<key>/<upload_id>/<part_num1>,<part_num2>,.../presigned

{
  "presignedUrls": {
    "part_num1": "https://s3.cesnet.cz/<presigned>",
    "part_num2": "https://s3.cesnet.cz/<presigned>",
  }
}
```

*Note:* the caller can use part numbers from the range of 1-9999 (S3 limitation), in any order.

*Note:* URL presigning is performed locally, it does not require a call to S3 server, so it is a relatively fast operation (just calling hmac signature for each url).

### Uploading part directly to S3

Normal s3 upload is performed on the presigned url, see https://docs.aws.amazon.com/AmazonS3/latest/API/API_UploadPart.html

```
PUT "https://s3.cesnet.cz/<presigned>"
<part content>

response:
ETag: ...
```

*Note:* The client needs to keep the part number and etag and use it in the completion request.

### Completing the upload

https://docs.aws.amazon.com/AmazonS3/latest/API/API_CompleteMultipartUpload.html

```
POST /draft/records/<id>/files/<key>/<upload_id>/complete

{
   parts: [
    {
      "PartNumber": 1,
      "ETag": "..."
    },
    {
      "PartNumber": 2,
      "ETag": "..."
    },
  ]
}
```

This call at first calls upload complete
call on S3 API and subsequently finalizes
invenio upload.

Alternative APIs
---

* We have considered adding an "S3" compatible API directly to Invenio, so that invenio could act as S3 gateway. It does not work as clients "invent" the url for uploading parts, using the "invenio" base url and thus all the traffic would have to go through invenio.

* We have also considered not using invenio at all for initiating the upload. We'd set a temporary access to an S3 bucket (can't use presigned urls in this scenario) and upon completion would take the ownership of the created object and register it in invenio. This alternative was refused from the security perspective (creating users, extra buckets, taking ownership, ...)

Proposed REST API
---

During multipart initiation, client specifies the  requested number of parts.

Until the record is committed, presigned urls are returned as part of `links` section, everytime the client gets the file resource. They are created fresh for each `GET` request. URL presigning is performed locally, it does not require a call to S3 server so it is a relatively fast operation (still includes hmac for each url).

The presigned urls are returned only if the user has permission to upload files to the record (or, alternatively, only to the identity which initiated the upload).


**Advantages**

API simpler than in oarepo-s3

**Disadvantages**

More work is performed on the backend - anytime GET is performed, presigned urls need to be created.

Can not have a streaming upload when the size of the data (and number of parts) is not known in advance. Unclear if we need this use case.


### Multipart initiation
```
POST /api/records/<id>/draft/files
payload:
[{
  "key": "dataset.zip",
  "storage_class": "M", // or maybe even "L"?
  "parts": 20
}]

response:
{
  "entries": [{
    ... standard invenio response
    "status": "pending",
    "links": {
      "self": ".../files/dataset.zip",
      "parts": [
         {
             "part": 1,
             "url": "https://s3.cesnet.cz/<presigned>",
             "expiration": "<utc datetime iso format>"
         },...
      ],
      "uploaded_parts": "...",
      "commit": ".../files/dataset.zip/commit"
    }
  }]
}
```

Later on:

```
GET /api/records/<id>/draft/files/dataset.zip

response:
{
  ... standard invenio response
  "status": "pending",
  "links": {
    "self": ".../files/dataset.zip",
    "parts": [
       {
           "part": 1,
           "url": "https://s3.cesnet.cz/<different_presigned>",
           "expiration": "<newer utc datetime>"
       },...
    ],
    "uploaded_parts": "...",
    "commit": ".../files/dataset.zip/commit"
  }
}
```

I have intentionally omitted the `content` link as it should not be called before the upload has finished.

The `uploaded_parts` link would be an invenio endpoint that would internally call https://docs.aws.amazon.com/AmazonS3/latest/API/API_ListParts.html and convert the result to

```
{
  "links": {
     "self": "...",
     "next": "..."
  },
  "parts": [
    {
      "part": 1,
      "checksums": {
        "crc32": "...",
        "crc32c": "...",
        "sha1": "...", ...
      },
      "etag": "",
      "modified": "...",
      "size": 1234
    }
  ]
}
```

### Uploading part directly to S3

Normal S3 part upload here via a `PUT` to presign url.

### Committing the upload

```
POST .../files/dataset.zip/commit

200 OK
```

### Retrieving file from S3

Getting the `content` url would return an HTTP 302 with `Location` header being the pre-signed request to S3.

The current implementation returns HTTP code 200 (with a correct Location header), needs to be changed to 302. 

   
Alternative REST API A
---

Presigned urls for parts are created during multipart initiation. They are created only once and not returned in subsequent GET requests.

This API can be used only for S3 instances with longer expiration policies. In CESNET, we have the expiration set to 1 hour, so users with large uploads on slow network might not be able to upload the dataset in time.

**Advantages**

Simple API

**Disadvantages**

Works only in some scenarios on fast network, if it does not work there is no upload alternative. 

Alternative REST API B
---

This alternative closely follows what oarepo-s3 does.

**Advantages**

Less work performed on server for each step, will be
more noticeable on uploads with many parts that take a long time.

**Disadvantages**

Extra API call, less elegant API


Invenio changes
---

### Multipart initiation (create new file)

```
FileService.init_files()
  run_components()
    FileMetadataComponent.init_files()
      Transfer.get_transfer()
        transfer.init_file()
          record.files.create()
            <FileRecord>.create()
    MultipartUploadInitComponent.init_files()
      <create multipart upload to s3>
      <store record_uuid, upload_id, parts number, expiration to local db>
      <create presigned urls and put them temporarily to record>
  file_result_list()
    FileList()
      to_dict()
        links.expand()
          MultipartUploadLinks.expand()
   
FileService.commit_file()
```

**Required invenio modifications:**
Keeping "L" transfer type:
* InitFileSchema - remove "parts" from metadata
* Add MultipartUploadInitComponent as above
* If we do not mind having "parts" in metadata, no modifications of existing invenio code are required for the upload initiation.

"M" transfer type:
* Transfer.init_file: remove "parts" from metadata
* inside the M transfer perform whatever is in MultipartUploadInitComponent.init_files()

### Multipart commit

```
FileService.commit_file()
  run_components()
    MultipartUploadCommitComponent.commit_file(<payload>)
      <complete upload in s3 s3>
      <create object version>
    FileMetadataComponent.commit_file()
      Transfer.get_transfer()
        transfer.commit_file()
          # checks that object version is created
```

**Required invenio modifications:**

Keeping "L" transfer type:
* Implement MultipartUploadCommitComponent

"M" transfer type:
* Implement the content of MultipartUploadCommitComponent inside the commit_file of the transfer

*Note:* We need to set the checksum on the invenio's FileInstance. As S3 does not return an "external" checksum for files uploaded via multipart, we store a dummy checksum `etag:<s3 etag>`. 

### GET file (`/records/<id>/draft/files/<key>`)

If upload is in process, a component `MultipartUploadStatusComponent` will create the presigned urls. MultipartUploadLinks (registered inside ) will serialize those to `links`.


Current implementation
---

**Note:** The implementation inside oarepo-s3 is obsolete and will not work with current InvenioRDM. It is based on our drafts library (replaced with invenio-drafts-resources) and on its own implementation of files support, which included extensible framework for file upload/retrieval handlers. The handlers are called one after another (similarly to service components) and the first one that can handle the upload wins.
In our case, the upload handler looks if the url contains the ?multipart query and if so it kicks in.

