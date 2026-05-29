import base64
import gzip
from typing import Any
import xml.etree.ElementTree as ET
import os
import shutil
from pathlib import Path
import urllib.request
import urllib.parse
import urllib.error

# finds the name of the game folder
def find_game_dir() -> str:
	localappdata = os.getenv("LOCALAPPDATA")
	if not localappdata:
		raise ValueError("You don't appear to be on Windows")
	requirements = {"CCLocalLevels.dat", "CCGameManager.dat"} # every gd has these
	for subdir in Path(localappdata).iterdir():
		if subdir.is_dir():
			try:
				contained_files = {file.name for file in subdir.iterdir() if file.is_file()}
				if requirements.issubset(contained_files):
					return f"{subdir}{os.sep}"
			except Exception:
				continue # some folders may restrict viewing access, they are not the correct folder
	raise ValueError("You don't appear to have Geometry Dash installed! If you do, make sure you ran it and closed it **at least once** or else this program will fail!")

gamedir = find_game_dir()

## Encryption ##
def xor(string: str, key: int = 11) -> str:
	return ("").join(chr(ord(char) ^ key) for char in string)

def gzip_data(data: str) -> str:
	return base64.urlsafe_b64encode(gzip.compress(data.encode())).decode()

def ungzip_data(data: str) -> str:
	return gzip.decompress(base64.urlsafe_b64decode(data.encode())).decode()

# cocos plist format
def parse_plist(element: ET.Element) -> dict[str, Any]:
	result: dict[str, Any] = {}
	items = list(element)
	for i in range(0, len(items), 2):
		key = items[i].text
		if not key:
			continue
		value_node = items[i+1]

		if value_node.tag == 'i':
			result[key] = int(value_node.text or "")
		elif value_node.tag == 'r':
			result[key] = float(value_node.text or "")
		elif value_node.tag == 's':
			result[key] = value_node.text
		elif value_node.tag == 'd':
			parsed = parse_plist(value_node)
			if parsed.get("_isArr"):
				result[key] = [value for key, value in parsed.items() if key.startswith("k_")]
			else:
				result[key] = parsed
		elif value_node.tag == 't':
			result[key] = True
		elif value_node.tag == 'f':
			result[key] = False
	return result

def dict_to_plist(data: dict[str, Any]) -> ET.Element:
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
		elif isinstance(value, list):
			value_node = dict_to_plist({"_isArr": True, **{f"k_{i}": val for i, val in enumerate(value)}})
			root.append(value_node)
		else:
			value_node = ET.SubElement(root, 's')
			value_node.text = str(value)

	return root

# convert plist to XML
def parse_plist_data(data: str) -> dict:
	el = ET.fromstring(data).find("dict")
	if el is None:
		raise ValueError("Invalid plist data")
	return parse_plist(el)

def unparse_plist_data(data: dict) -> str:
	root = dict_to_plist(data)
	root.tag = "dict"
	plist_root = ET.Element("plist", attrib={"version": "1.0", "gjver": "2.0"})
	plist_root.append(root)
	return gzip_data(xor(ET.tostring(plist_root, "unicode", xml_declaration=True)))

# Helper functions to simplify this
def parse_gamedata(type: str = "CCLocalLevels.dat") -> dict:
	with open(gamedir + type, "r") as f:
		return parse_plist_data(ungzip_data(xor(f.read())))

def save_gamedata(data: dict, type: str = "CCLocalLevels.dat") -> None:
	with open(gamedir + type, "w") as f:
		f.write(xor(gzip_data(unparse_plist_data(data))))

## Downloading levels ##

# replaces requests.post to stay fully built-in libraries
def requests_post(url: str, data: dict, *, headers: dict) -> str:
	req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode("utf-8"), headers=headers, method="POST")
	try:
		return urllib.request.urlopen(req).read().decode("utf-8")
	except urllib.error.URLError:
		raise ValueError("Failed to make request")

# searches levels
def search_levels(query: str) -> list[tuple[int, str]]:
	url = "http://www.boomlings.com/database/getGJLevels21.php"
	req = requests_post(url, data={ "str": query, "type": 0, "secret": "Wmfd2893gb7" }, headers={ "User-Agent": "" })
	levels = []
	for server_level in req.split("#")[0].split("|"):
		as_dict = dict(zip(server_level.split(':')[::2], server_level.split(':')[1::2]))
		levels.append((int(as_dict["1"]), as_dict["2"]))
	return levels

# downloads a level; returning a strange format which you can learn about on boomlings.dev
def download_level(id: int) -> str:
	url = "http://www.boomlings.com/database/downloadGJLevel22.php"
	req = requests_post(url, data={ "levelID": id, "secret": "Wmfd2893gb7" }, headers={ "User-Agent": "" })
	return req

# adds level to save file
def convert_server_to_client_level(server_level: str) -> dict:
	as_dict = dict(zip(server_level.split(':')[::2], server_level.split(':')[1::2]))
	return {'kCEK': 4, 'k2': as_dict["2"], 'k5': 'Player', 'k13': True, 'k21': 2, 'k16': 1, 'k50': 45, "k8": int(as_dict.get("12", 0)), "k45": int(as_dict.get("35", 0)), "k4": as_dict["4"]}

def add_level_to_save_file(id: int):
	data = parse_gamedata()

	level_data = download_level(id).split("#")[0]
	data["LLM_01"].insert(0, convert_server_to_client_level(level_data))

	save_gamedata(data)

# Adds a song on the local machine to the save file
def add_song_to_save_file(audio_path: str, id: int, name: str, author: str):
	data = parse_gamedata("CCGameManager.dat")

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

	save_gamedata(data, "CCGameManager.dat")