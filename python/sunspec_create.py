# creates a sunSpec_specification class from GitHub SunSpec sources

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

# optimize dstring by removing trailing padding
def sunspec_remove_padding(dstring, names):
    while len(dstring) > 0 and dstring[-1] == "x":
        dstring = dstring[:-1]
        names = names[:-1]
    return dstring, names

# connect to GitHub
username = "dersecure"
g = Github()
user = g.get_user(username)
repo = g.get_repo("sunspec/Models")

code = ""
current_utc_time = datetime.now(timezone.utc)

# downlaod github repository (default branch)
download_url = repo.get_archive_link("zipball", ref=repo.default_branch)
response = requests.get(download_url)
zipfile = zipfile.ZipFile(io.BytesIO(response.content))
# process all files which belongs to the json folder and are valid models
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
    
    types = ""
    names = []
    count = 0

    print("group id:", jsonobj["id"], ", group name:", jsonobj["group"]["name"])

    grouping = jsonobj["group"]["points"]
    round = 1
    while grouping is not None:
        for point in grouping:
            type = point["type"]
            size = 1
            if point["size"] > 1:
                size = point["size"]
            if type == "int16" or type == "sunssf":
                type = "h"
                size = 1
            elif type == "uint16" or type == "bitfield16" or type == "enum16" or type == "acc16" or type == "raw16":
                type = "H"
                size >>= 1 
            elif type == "int32":
                type = "l"
                size >>= 2
            elif type == "uint32" or type == "bitfield32" or type == "acc32" or type == "enum32":
                type = "L"
                size >>= 2
            elif type == "int64":
                type = "q"
                size >>= 3
            elif type == "uint64" or type == "acc64" or type == "bitfield64":
                type = "Q"
                size >>= 3
            elif type == "float32":
                type = "f"
                size >>= 2
            elif type == "string":
                type = "s"
            elif type == "pad":
                type = "x"
            elif type == "eui48":
                type = "c"
                size *= 6
            elif type == "ipv6addr":
                type = "c"
                size *= 16
            elif type == "ipaddr":
                type = "c"
                size *= 4
            elif type == "count":
                type = "_"
                if round == 2:
                    raise Exception("nested group are not supported")
                if size > 1:
                    raise Exception("count field with size > 1 not supported")
                size >>= 1 
                count = 1
            else:
                print("unknown type:", point["type"])
                exit()  
            if size > 1:
                types += str(size)
            types += type
            names.append(point["name"]) 
        if count == 1 and round == 1:
            # add padding for count
            types += "_"
            names.append("")
            grouping = jsonobj["group"]["groups"][0]["points"]
            count = 0
            round = 2
        else:
            grouping = None   
    
    types, names = sunspec_remove_padding(types, names)
    # print("names:", names)
    # print("types:", types)

    if code != "":
        code += ",\n"
    code += "\t" + str(jsonobj["id"]) 
    code += ": (\"" + jsonobj["group"]["name"] 
    code += "\", \"" + types 
    code += "\", [\"" + "\", \"".join(names) + "\"])" 

# write code to sunspec_specification.py
code = "# created by sunspec_create.py (" + str(current_utc_time) + ")\n"# source https://github.com/sunspec/models/tree/master/json \n\nclass SunSpec_Specification:\n\tSpecification = {\n" + code + "}\n"
fd = os.open(os.path.dirname(os.path.abspath(__file__)) + "/sunspec_specification.py", os.O_CREAT | os.O_WRONLY, 0o666)
os.write(fd, code.encode())
os.close(fd)

