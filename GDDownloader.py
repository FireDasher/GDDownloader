import tkinter as tk
from tkinter import messagebox, filedialog
from geometryDash import search_levels, add_level_to_save_file, add_song_to_save_file, find_game_dir

gamedir = find_game_dir()
if gamedir is None:
	messagebox.showerror("Error", "No game directory found!!!")

def download(id: int):
	try:
		add_level_to_save_file(gamedir, id)
	except Exception as e:
		messagebox.showinfo("Download unseccesful", f"Download of {id} FAILED!!!\nThis is usually because you are using school WiFi! Make sure you are using your phone hotspot!\nError Code:\n{e}")
		return
	messagebox.showinfo("Download succesful", f"Succesfully downloaded {id}")

def search():
	try:
		results = search_levels(search_input.get())
	except Exception as e:
		messagebox.showinfo("Search unseccesful", f"Search of {search_input.get()} FAILED!!!\nThis is usually because you are using school WiFi! Make sure you are using your phone hotspot!\nError Code:\n{e}")
		return

	for widget in levels_frame.winfo_children(): widget.destroy()
	for i, level in enumerate(results):
		tk.Label(levels_frame, text=str(level[0])).grid(column=0, row=i)
		tk.Label(levels_frame, text=level[1]).grid(column=1, row=i)
		tk.Button(levels_frame, text="Get", command=(lambda val=level[0]: download(val))).grid(column=2, row=i)

def add_song():
	path = filedialog.askopenfilename(title="Select the song file")
	if path != "":
		try:
			add_song_to_save_file(gamedir, path, int(id_input.get()), title_input.get(), "Someone")
		except Exception as e:
			messagebox.showinfo("Adding song unseccesful", f"Adding song FAILED!!!\nThis should not be able to fail so you must've done something very wrong\nError code:\n{e}")
			return
		messagebox.showinfo("Adding song succesful", f"Succesfully added song")

root = tk.Tk()
root.title("GD Downloader")
root.geometry("1000x500")

tk.Label(root, text=f"Detected game directory: {gamedir}").pack(pady=20)

tk.Label(root, text="Search for levels").pack()

search_input = tk.Entry(root)
search_input.pack()

tk.Button(root, text="Search", command=search).pack()

levels_frame = tk.Frame(root, relief="solid", borderwidth=1)
tk.Label(levels_frame, text="Click \"Search\" to search!").grid(row=0,column=0)
levels_frame.pack(pady=20)

tk.Label(root, text="Add song to your saved songs list (id, title, add) (You need to manually download the song file)").pack()
id_input = tk.Entry(root)
id_input.insert(0, "123456")
id_input.pack()
title_input = tk.Entry(root)
title_input.insert(0, "Song")
title_input.pack()
tk.Button(root, text="Select song file and add", command=add_song).pack()

root.mainloop()