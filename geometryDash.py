import base64, gzip
import xml.etree.ElementTree as ET
import os, shutil
from pathlib import Path
import urllib.request, urllib.parse, urllib.error

## Encryption ##
def xor(string: str, key: int) -> str:
	return ("").join(chr(ord(char) ^ key) for char in string)

def decrypt_data(data: str) -> str:
	base64_decoded = base64.urlsafe_b64decode(xor(data, key=11).encode("utf-8"))
	decompressed = gzip.decompress(base64_decoded)
	return decompressed.decode("utf-8")

def encrypt_data(data: str) -> str:
	gzipped = gzip.compress(data.encode("utf-8"))
	base64_encoded = base64.urlsafe_b64encode(gzipped)
	return xor(base64_encoded.decode("utf-8"), key=11)

# stupid abbreviated plist format
def parse_plist(element: ET.Element) -> dict:
    result = {}
    items = list(element)
    for i in range(0, len(items), 2):
        key = items[i].text
        value_node = items[i+1]

        if value_node.tag == 'i':
            result[key] = int(value_node.text)
        elif value_node.tag == 'r':
            result[key] = float(value_node.text)
        elif value_node.tag == 's':
            result[key] = value_node.text
        elif value_node.tag == 'd':
            result[key] = parse_plist(value_node)
        elif value_node.tag == 't':
            result[key] = True
        elif value_node.tag == 'f':
            result[key] = False
    return result

def dict_to_plist(data: dict) -> ET.Element:
	root = ET.Element('d')

	for key, value in data.items():
		key_node = ET.SubElement(root, 'k')
		key_node.text = str(key)

		if isinstance(value, bool):
			value_node = ET.SubElement(root, 't') if value else ET.SubElement(root, 'f')
		elif isinstance(value, int):
			value_node = ET.SubElement(root, 'i')
			value_node.text = str(value)
		elif isinstance(value, float):
			value_node = ET.SubElement(root, 'r')
			value_node.text = str(value)
		elif isinstance(value, dict):
			value_node = dict_to_plist(value)
			root.append(value_node)
		else:
			value_node = ET.SubElement(root, 's')
			value_node.text = str(value)

	return root

# combine encryption and plist
def parse_save_data(data: str) -> dict:
	return parse_plist(ET.fromstring(decrypt_data(data)).find("dict"))

def unparse_save_data(data: dict) -> str:
	fkjsa = dict_to_plist(data)
	fkjsa.tag = "dict"
	plist_root = ET.Element( "plist", attrib={"version": "1.0", "gjver": "2.0"} )
	plist_root.append(fkjsa)
	return encrypt_data(ET.tostring(plist_root, "unicode", xml_declaration=True))

# finds the name of the game folder
def find_game_dir() -> str:
	localappdata = os.getenv("LOCALAPPDATA")
	if not localappdata: raise ValueError("asdfjkl")
	requirements = {"CCLocalLevels.dat", "CCGameManager.dat"} # every gd has these
	for subdir in Path(localappdata).iterdir():
		if subdir.is_dir():
			try:
				contained_files = {file.name for file in subdir.iterdir() if file.is_file()}
				if requirements.issubset(contained_files):
					return f"{subdir}{os.sep}"
			except:
				continue # some folders may restrict viewing access, they are not the correct folder
	# raise ValueError("You don't appear to have Geometry Dash installed! If you do, make sure you ran it and closed it **at least once** or else this program will fail!")
	return None

## Downloading levels ##

#server related stuff

# replaces requests.post to stay fully built in libraries
def requests_post(url: str, data: dict, *, headers: dict) -> str:
	req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode("utf-8"), headers=headers, method="POST")
	try:
		return urllib.request.urlopen(req).read().decode("utf-8")
	except urllib.error.URLError as e:
		raise ValueError("Failed to make request")

def search_levels(query: str) -> list[tuple[int, str]]:
	url = "http://www.boomlings.com/database/getGJLevels21.php"
	req = requests_post(url, data={ "str": query, "type": 0, "secret": "Wmfd2893gb7" }, headers={ "User-Agent": "" })
	levels = []
	for server_level in req.split("#")[0].split("|"):
		as_dict = dict(zip(server_level.split(':')[::2], server_level.split(':')[1::2]))
		levels.append((int(as_dict["1"]), as_dict["2"]))
	return levels

def download_level(id: int) -> str:
	url = "http://www.boomlings.com/database/downloadGJLevel22.php"
	req = requests_post(url, data={ "levelID": id, "secret": "Wmfd2893gb7" }, headers={ "User-Agent": "" })
	return req

# this simply appends something to the front of the array which is in a weird dictionary format
def unshift_array_dict(d: dict, new_element):
	if not d.get("_isArr"):
		raise ValueError("Not a valid array-like dictionary")

	items = []
	for i in range(len([k for k in d.keys() if k.startswith("k_")])):
		items.append(d.pop(f"k_{i}"))

	d["k_0"] = new_element
	for i, item in enumerate(items):
		d[f"k_{i+1}"] = item

# adds level to save file
def convert_server_to_client_level(server_level: str) -> dict:
	as_dict = dict(zip(server_level.split(':')[::2], server_level.split(':')[1::2]))
	return {'kCEK': 4, 'k2': as_dict["2"], 'k5': 'Player', 'k13': True, 'k21': 2, 'k16': 1, 'k50': 45, "k8": int(as_dict.get("12", 0)), "k45": int(as_dict.get("35", 0)), "k4": as_dict["4"]}

def add_level_to_save_file(gamedir: str, id: int):
	with open(os.path.expandvars(gamedir + "CCLocalLevels.dat"), "r") as f:
		data = parse_save_data(f.read())
	level_data = download_level(id).split("#")[0]
	unshift_array_dict(data["LLM_01"], convert_server_to_client_level(level_data))
	with open(os.path.expandvars(gamedir + "CCLocalLevels.dat"), "w") as f:
		f.write(unparse_save_data(data))

# Adds song to the save file, this doesn't download it from newgrounds so you gotta do that yourself
def add_song_to_save_file(gamedir: str, audio_path: str, id: int, name: str, author: str):
	with open(os.path.expandvars(gamedir + "CCGameManager.dat"), "r") as f:
		data = parse_save_data(f.read())

	shutil.copy(audio_path, os.path.expandvars(gamedir + f"{id}.mp3"))

	data["MDLM_001"][id] = {
		"kCEK": 6,
		"1": int(id),
		"2": name,
		"3": 30,
		"4": author,
		"5": os.path.getsize(audio_path)/1048576,
		"9": 1,
	}

	with open(os.path.expandvars(gamedir + "CCGameManager.dat"), "w") as f:
		f.write(unparse_save_data(data))

# from tkinter import filedialog
# from geometryDash import add_song_to_save_file

# if __name__ == "__main__":
# 	audio_path = filedialog.askopenfilename()
# 	if audio_path != "":
# 		id = input("id: ")
# 		name = input("name: ")

# 		add_song_to_save_file(audio_path, id, name, "Someone")

# from geometryDash import add_level_to_save_file

# # def convert_server_level_to_local_level(server_level: str) -> dict:
# # 	as_dict = dict(zip(server_level.split(':')[::2], server_level.split(':')[1::2]))
# # 	return {
# # 		"k1": int(as_dict["1"]),
# # 		"k2": as_dict["2"],
# # 		"k3": as_dict["3"],
# # 		"k4": as_dict["4"],
# # 	}

# # def append_to_sequential_dict(d: dict, value):
# # 	if not d or d == {"_isArr": True}:
# # 		next_index = 0
# # 	else:
# # 		max_index = max(int(k.split("_")[1]) for k in d.keys() if k != "_isArr")
# # 		next_index = max_index + 1

# # 	new_key = f"k_{next_index}"
# # 	d[new_key] = value

# # def override_last_level(d: dict, server_level: str):
# # 	as_dict = dict(zip(server_level.split(':')[::2], server_level.split(':')[1::2]))
# # 	d[f"k_0"]["k4"] = as_dict["4"]

# if __name__ == "__main__":
# 	# CraZy II: 47620786
# 	id = int(input("level ID: "))
# 	add_level_to_save_file(id)