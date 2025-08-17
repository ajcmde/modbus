#
# This is free and unencumbered software released into the public domain.
#
# Anyone is free to copy, modify, publish, use, compile, sell, or
# distribute this software, either in source code form or as a compiled
# binary, for any purpose, commercial or non-commercial, and by any
# means.
#
# In jurisdictions that recognize copyright laws, the author or authors
# of this software dedicate any and all copyright interest in the
# software to the public domain. We make this dedication for the benefit
# of the public at large and to the detriment of our heirs and
# successors. We intend this dedication to be an overt act of
# relinquishment in perpetuity of all present and future rights to this
# software under copyright law.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
# 
# For more information, please refer to <https://unlicense.org>
#

# Pre-requisites
#   pip install PyGithub
# Specification Type 701: https://github.com/sunspec/models/blob/master/json/model_701.json

import json
import time
import datetime
import requests
import zipfile
import io
import os
from datetime import datetime, timezone
from github import Github

username = "dersecure"
# Public Web Github
g = Github()
user = g.get_user(username)
repo = g.get_repo("sunspec/Models")

code = ""
current_utc_time = datetime.now(timezone.utc)

download_url = repo.get_archive_link("zipball", ref=repo.default_branch)
response = requests.get(download_url)
zipfile = zipfile.ZipFile(io.BytesIO(response.content))
for zipinfo in zipfile.infolist():
    if zipinfo.is_dir():
        continue
    if os.path.basename(os.path.dirname(zipinfo.filename)) != "json":
        continue
    filename = os.path.basename(zipinfo.filename)
    if not filename.startswith("model_") or not filename.endswith(".json"):
        continue
    number = int(filename.split("_")[1].split(".")[0])
    # exlude test schemas
    if number > 63000:
        continue

    file = zipfile.open(zipinfo)
 
    jsonobj = json.loads(file.read().decode())
    file.close()
    
    specs = {}
    count = 0
    offset = 0
 

    def AppendCode(code, specs, id, subid, group_name):
        if code != "":
            code += ",\n"
        code += "\t(" + str(id) + ", " + str(subid) + ")"
        code += ": (\"" + str(group_name) 
        code += "\", " + str(specs) 
        code += ")" 
        return code

    print("group id:", jsonobj["id"], ", group name:", jsonobj["group"]["name"])

    subid = 0
    count = 0
    while subid <= count:
        if subid == 0:
            grouping = jsonobj["group"]["points"]
        else:
            grouping = jsonobj["group"]["groups"][subid - 1]["points"]
        for point in grouping:
            type = point["type"]
            if point["size"] > 1:
                size = point["size"]
            else:
                size = 1
            if type == "count":
                count += 1
            if "units" in point:
                units = "[" + point["units"] + "]"
            else:
                units = ""

            specs[offset] = (point["name"] + units, type, size)
            offset += size

        code = AppendCode(code, specs, jsonobj["id"], subid, jsonobj["group"]["name"])
        subid += 1


code = "# created by sunspec_create.py (" + str(current_utc_time) + ")\n# source https://github.com/sunspec/models/tree/master/json \n# Copyright and Trademark: SunpSpec Alliance: Apache License https://github.com/sunspec/models/blob/master/LICENSE \n\nclass SunSpec_Specification:\n\tSpecification = {\n" + code + "}\n"
fd = os.open(os.path.dirname(os.path.abspath(__file__)) + "/sunspec_specification.py", os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o666)
os.write(fd, code.encode())
os.close(fd)
