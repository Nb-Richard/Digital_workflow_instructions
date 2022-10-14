# Import libraries
import streamlit as st
import json
from json import JSONEncoder
import base64
import os
import glob
import filetype
import pandas as pd
from PIL import Image
from streamlit_drawable_canvas import st_canvas
import io
import time
import random
from paho.mqtt import client as mqtt_client


# Adjust page configurations
st.set_page_config(page_title="Work Instruction Manager",layout="wide")

broker = 'broker.emqx.io'
port = 1883
topic = "python/mytest/mqtt"
# generate client ID with pub prefix randomly
client_id = f'python-mqtt-{random.randint(0, 1000)}'
username = 'emqx'
password = 'public'

if 'step_array' not in st.session_state:
    st.session_state.step_array = []

if 'msg_count' not in st.session_state:
    st.session_state.msg_count = 1


# Class declarations
class WorkInstruction:			# Class for a work instruction that is initialized when a new WI is created
	def __init__(self, wi_name, wi_desc, wi_id, wi_steps):
		self.wi_name = wi_name
		self.wi_desc = wi_desc
		self.wi_id = wi_id
		self.wi_steps = wi_steps

class AnotherWorkInstruction:	# Class for a work instruction when reading and decoding from the JSON file
	def __init__(self, dict):
		self.__dict__.update(dict)

class Step:						# Class for a step in the work instruction when a new step is created
	def __init__(self, step_name, step_desc, step_visual, step_inputs):
		self.step_name = step_name
		self.step_desc = step_desc
		self.step_visual = step_visual
		self.step_inputs = step_inputs
		self.step_inputs_no = len(step_inputs)

class AnotherStep:				# Class for a step in the work instruction when reading and decoding from the JSON file
	def __init__(self, dict):
		self.__dict__.update(dict)

class Input:					# Class for an input field in the step
	def __init__(self, input_name, input_type):
		self.input_name = input_name
		self.input_type = input_type

class TextField(Input):			# Subclass of text filed type Input() objects
	def __init__(self, input_name, destination):
		self.destination = destination
		super().__init__(input_name,'text input')

class Button(Input):			# Subclass of button type Input() objects
	def __init__(self, input_name, function):
		self.function = function
		super().__init__(input_name,'button')

class WIEncoder(JSONEncoder):	# Custom JSON encoder for the step, work instruction and input field class objects that otherwise cannot be encoded
	def default(self,obj):
		if type(obj).__name__ == "Step" or type(obj).__name__ == "AnotherStep" or type(obj).__name__ == "WorkInstruction" or type(obj).__name__ == "AnotherWorkInstruction"or type(obj).__name__ == "TextField" or type(obj).__name__ == "Button":
			return obj.__dict__	# Encode the above class objects using their __dict__ attribute
			# Not recommended to use built-in Python methods/attributes, try to see if it is possible to optimize and fina another alternative
		else:
			return json.JSONEncoder.default(self,obj)	# Encode all other data types normally


# Function and variable declarations
def edit_wi(file_path):			# Function to change to editor mode upon selecting the work instruction to edit
	st.session_state.page_mode = "edit"
	st.session_state.wi_file_path = file_path
	load_wi(file_path)

def deploy_wi(file_path):		# Function to change to deploy mode upon selecting the work instruction to deploy
	st.session_state.page_mode = "deploy"
	load_wi(file_path)
	t = time.time()
	st.session_state.step_array.append(t)

def edit_photo():
	st.session_state.page_mode = "edit_photo"
	
def create_new_wi():			# Function to create a new work instruction object and JSON file path
	st.session_state.page_mode = "new_wi"


def delete_wi(file_path):	# Function to delete a new work instruction object and JSON file path
	if os.path.exists(file_path):
		os.remove(file_path)
	else:
		print("The file does not exist")


def add_visual_guide():			# Function to add a media file from the file_uploader widget to the list of visual guide files
	if visual_guide_upload is not None:
		st.session_state.step_visual_list[st.session_state.step_index].append(visual_guide_upload.read())	# Copy IOBytes file from camera_input and append it to list of visual guides
	if visual_guide_upload1 is not None:
		st.session_state.step_visual_list[st.session_state.step_index].append(visual_guide_upload1.read())  # Copy IOBytes file from file_uploader and append it to list of visual guides
	
def save_photo():			# Function to add a media file from the file_uploader widget to the list of visual guide files
	if canvas_image is not None:
		st.session_state.step_visual_list[st.session_state.step_index].append(canvas_image)

def load_wi(read_directory):	# Function to load a work instruction from JSON file, called through callback from edit button
	st.session_state.step_list = []			# Create empty lists in st.session_state to store the loaded data
	st.session_state.step_visual_list = []
	with open(read_directory,"r") as load_file_test:	# Open file in file directory to read
		load_file_content = json.loads(load_file_test.read(),object_hook = AnotherWorkInstruction)	# Create work instruction object to save data from JSON file
		st.session_state.wi_name = load_file_content.wi_name	# Load variables from file session state variables
		st.session_state.wi_desc = load_file_content.wi_desc
		st.session_state.wi_id = load_file_content.wi_id

		for step in load_file_content.wi_steps:		# Load each step in st.session_state to persist between changes
			st.session_state.step_list.append(step)
			temp_visual_list = []	# Declare empty list to compile
			for media_file in step.step_visual:
				temp_visual_list.append(base64.b64decode(bytes(media_file,'utf-8')))	# Decode media files saved in JSON file from utf-8 string->base64 bytes->binary file type
			st.session_state.step_visual_list.append(temp_visual_list)	# Append the list of visual guide files for each step

def save_wi(write_directory):	# Function to save a work instruction to JSON file, called through callback from save work instruction button
	if step_select != "--Choose a step to edit--":
		st.session_state.step_list[st.session_state.step_index].step_name = step_title	# Save changes in step title and description to st.session_state before exporting to JSON file
		st.session_state.step_list[st.session_state.step_index].step_desc = step_desc
		st.session_state.step_select_dropdown = st.session_state.step_list[st.session_state.step_index].step_name	# Save the current step title into the dropdown list options

	step_index = range(len(st.session_state.step_visual_list))
	for index in step_index:	# Loop through each step to write into JSON file
		temp_visual_list = []
		for file in st.session_state.step_visual_list[index]:
			temp_visual_list.append(base64.b64encode(file).decode('utf-8'))	# Encode the media files for visual guides from binary data type->base64 bytes->utf-8 string
		st.session_state.step_list[index].step_visual = temp_visual_list	# Save media files into JSON file for each step
	temp_wi_object = WorkInstruction(wi_name,wi_desc,wi_id,st.session_state.step_list)	# Create WorkInstruction class object to write to JSON
	with open(write_directory,"w") as save_file_test:	# Open file in file directory to write
		save_file_test.write(json.dumps(temp_wi_object,indent = 2,cls=WIEncoder))	# Convert WorkInstruction class object to JSON string using dumps, using the custom encoder WIEncoder

def create_new_step():			# Function to create a new step and add to the work instruction
	del st.session_state["step_select_dropdown"]	# Delete the current dropdown widget to replace with the updated list of steps
	new_step = Step("Step " + str(len(st.session_state.step_list)+1),"",[],[])	# Create a new step as a Step() class object
	st.session_state.step_list.append(new_step)		# Add new step to list in st.session_state
	st.session_state.step_visual_list.append([])	# Declare blank list for media files for the visual guides of the new step

def switch_step_edit():			# Function to update the list of step titles, called through callback when switching to another step to edit
	if step_select != "--Choose a step to edit--":
		st.session_state.step_list[st.session_state.step_index].step_name = step_title
		st.session_state.step_list[st.session_state.step_index].step_desc = step_desc

def delete_step_edit():			# Function to delete a step from the work instruction
	# Work in Progress
	if len(st.session_state.step_list) < 1:
		st.error("The work instruction must have a minimum of 1 step.")
	elif st.session_state.step_index == 1:
		st.session_state.step_list.remove(st.session_state.step_index)
	else:
		st.session_state.step_list.remove(st.session_state.step_index)
		st.session_state.step_index += 1

def switch_step_deploy():		# Function to change the current step when a step is selected through the radio options
	st.session_state.display_state = 0		# Display state 0 will show the instructions for the step for the deployed work instruction
	st.session_state.step_index = step_select_list.index(st.session_state.step_select_radio)	# Update the step index to the current selected step

def switch_next_step_deploy():	# Function to change to the next step in the work instruction, called through callback function when next step button is clicked
	st.session_state.step_index += 1		# Increase the step index by 1. That's- that's it. Yea.
	st.session_state.step_select_radio = step_select_list[st.session_state.step_index]		# Update the radio option selection to the current step

def finish_steps_deploy():		# Function to change the display to the finish page when all steps in the work instructions are completed
	st.session_state.display_state = 1		# Display state 1 will show the finish page with summary for the deployed work instruction

def return_to_directory():		# Function to return to the directory of work instructions in the device
	for key in st.session_state.keys():
		del st.session_state[key]			# Clear all st.session_state variables and widget keys to start from default state


def connect_mqtt():
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print("Failed to connect, return code %d\n", rc)

    client = mqtt_client.Client(client_id)
    client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.connect(broker, port)
    return client

def publish(client):
    # msg_count = 1
    # step = [1665633050.6779158]
    # while True:
        
    t = time.time()
    st.session_state.step_array.insert(st.session_state.msg_count, t)
    # time.sleep(5)
    msg = f"step {st.session_state.msg_count} finished in: {int((st.session_state.step_array[st.session_state.msg_count] - st.session_state.step_array[st.session_state.msg_count-1])/60)}min {int((st.session_state.step_array[st.session_state.msg_count] - st.session_state.step_array[st.session_state.msg_count-1])%60)}s"
    result = client.publish(topic, msg)
    # result: [0, 1]
    status = result[0]
    if status == 0:
        print(f"Send `{msg}` to topic `{topic}`")
    else:
        print(f"Failed to send message to topic {topic}")
    st.session_state.msg_count += 1

def next_publish():
	switch_next_step_deploy()
	client = connect_mqtt()
	# client.loop_start()
	publish(client)

def finish_publish():
	finish_steps_deploy()
	client = connect_mqtt()
	# client.loop_start()
	publish(client)


# def return_to_edit_mode():	
# 	st.session_state.page_mode = "edit"

if 'page_mode' not in st.session_state:
	st.session_state.page_mode = "directory"

if st.session_state.page_mode == "directory":	# Directory mode: display the list of work instructions
	directory_path = "work-instruction-files\*.json"	# Declare folder path

	st.title("Work Instruction Manager")
	st.header("List of work instructions")

	# Create pseudo-table using st.columns to display the list of work instructions
	header_cols = st.columns([2,2,4,1,1,1])	# Declare headers of "table"
	header_cols[0].markdown("**Barcode ID**")
	header_cols[1].markdown("**WI Document Name**")
	header_cols[2].markdown("**WI Document Description**")

	directory_table = st.container()	# Content of tables are inserted here

	bottom_cols = st.columns(2)			# Just for aesthetics
	id_field = bottom_cols[0].text_input("Search for work instruction by ID or scan barcode")	# Input field to filter WI by ID/barcode
	new_wi = bottom_cols[0].button("Create new work instruction", on_click=create_new_wi)	# Button to create a new work instruction (Incomplete)

	wi_file_list = glob.glob(directory_path)	# Find all the files in the directory path folder, return as file paths
	file_index = 0
	for path in wi_file_list:		# Each iteration of for loop is a new row in the "table"
		wi_content = json.loads(open(path).read())

		if wi_content['wi_id'].startswith(id_field):	# Filter the work instruction based on the starting digits of the ID
		# if id_field in wi_content['wi_id']:			# Alternative option: Filter based on digits in any segment of the ID
			table_cols = directory_table.columns([2,2,4,1,1,1])
			table_cols[0].markdown(wi_content['wi_id'])
			table_cols[1].markdown(wi_content['wi_name'])
			table_cols[2].markdown(wi_content['wi_desc'])
			table_cols[3].button("Edit",key=("edit"+str(file_index)),on_click=edit_wi,args=(path,))		# Button to switch to editing page of the selected work instruction
			table_cols[4].button("Delete",key=("delete"+str(file_index)),on_click=delete_wi,args=(path,))	# Button to delete the selected work instruction
			table_cols[5].button("Deploy",key=("deploy"+str(file_index)),on_click=deploy_wi,args=(path,))	# Button to switch to deployment page of the selected work instruction
		file_index+=1


if st.session_state.page_mode == "new_wi":
	# Create new WI object here/declare variables in session_state
	st.session_state.step_list = []
	st.session_state.step_visual_list = []
	# Create a JSON file for the new WI
	# title = input("Enter the work instruction title: ")
	# id = input("Enter the work instruction id: ")
	# desc = input("Enter the work instruction description: ")
	with st.form("my_form"):
		wi_name = st.text_input("Enter the work instruction title 👇", placeholder="work instruction name")
		wi_id = st.text_input("Enter the work instruction id 👇", placeholder="work instruction id")
		wi_desc = st.text_area("Enter the work instruction description 👇", placeholder="work instruction description")
		submitted = st.form_submit_button("Create")
		if submitted:
			f = open(f"work-instruction-files\{wi_name}.json", "a")
			f.write('{')
			f.write(f'"wi_name": "{wi_name}", "wi_desc": "{wi_desc}","wi_id": "{wi_id}","wi_steps": [ ]')
			f.write('}')
			f.close()
			path = f"work-instruction-files\{wi_name}.json"
			edit_wi(path)


if st.session_state.page_mode == "edit":	# Edit mode: edit the selected work instruction
	step_name_list = []
	for step in st.session_state.step_list:
		step_name_list.append(step.step_name)	# Create list of step names used to create the dropdown list to select the step to edit

	wi_id = st.text_input("Id of work instruction",key="wi_id")			# Text input field to enter the name of the work instruction
	wi_name = st.text_input("Name of work instruction",key="wi_name")			# Text input field to enter the name of the work instruction
	wi_desc = st.text_area("Description of work instruction",key="wi_desc")		# Text area field to enter the description of the work instruction

	# Step selector to choose step to edit
	step_select_container = st.container()		# Dropdown list to select step will appear here
	step_select_list = ["--Choose a step to edit--"] + step_name_list	# Add a placeholder string to the front of the list

	col1,col2,col3,col4,col5 = st.columns(5)
	with col5:
		new_step_button = st.button("Create new step", on_click=create_new_step)	# Button to add a new step
	if new_step_button:
		st.session_state.step_select_dropdown = step_select_list[-1]				# Step index moves to the new step (last index)

	if 'step_select_dropdown' in st.session_state and st.session_state.step_select_dropdown != "--Choose a step to edit--":	# Only triggers after step select dropdown list has been initialized previously
		new_step_index = step_name_list.index(st.session_state.step_select_dropdown)	# Find index of the selected step in the list of step names
		st.session_state.step_select_dropdown = step_name_list[new_step_index]		# Update the step name in the dropdown options, if there were any changes

	step_select = step_select_container.selectbox("Step to edit",step_select_list,key="step_select_dropdown",on_change=switch_step_edit)	# Initialization of dropdown widget
	if step_select != "--Choose a step to edit--":
		st.session_state.step_index = step_name_list.index(st.session_state.step_select_dropdown)	# Find the index of the current step
		st.header("Currently editing: Step " + str(st.session_state.step_index+1))		# Display the current step number
		step_title = st.text_input("Step title",value=st.session_state.step_list[st.session_state.step_index].step_name,key="step_title")	# Input field for the step title
		step_desc = st.text_area("Enter description of step (detailed instructions, materials, etc.)",value=st.session_state.step_list[st.session_state.step_index].step_desc,key="step_description")	# Input field for the step description
		st.markdown("**(Optional) Add a visual guide as a video or image**")
		visual_guide_upload1 = st.file_uploader("Upload video or image guide here", type=['png','jpg','jpeg','mp4','wmv'])	# Media file uploader widget for the visual guides
		visual_guide_upload = st.camera_input("Take a photo for visual guide", key ="visual_guide_upload")
		canvas_image = None # Declare the variable canvas_image

		if st.checkbox('Edit photo'): # Display canvas to edit photo
			# Specify canvas parameters in application
			drawing_mode = st.sidebar.selectbox(
				"Drawing tool:", ("freedraw", "point", "line", "rect", "circle", "transform")
			)

			stroke_width = st.sidebar.slider("Stroke width: ", 1, 25, 3)
			if drawing_mode == 'point':
				point_display_radius = st.sidebar.slider("Point display radius: ", 1, 25, 3)
			stroke_color = st.sidebar.color_picker("Stroke color hex: ")
			bg_color = st.sidebar.color_picker("Background color hex: ", "#eee")
			# bg_image = st.image(visual_guide_upload)

			realtime_update = st.sidebar.checkbox("Update in realtime", True)

			# get the visual_guide_upload photo size
			if visual_guide_upload:
				img = Image.open(visual_guide_upload)
				w, h = img.size 
			else:
				w, h = 700, 300	

			# Assign them to new variables
			canvas_width = w
			canvas_height = h

			# Create a canvas component
			canvas_result = st_canvas(
				fill_color="rgba(255, 165, 0, 0.3)",  # Fixed fill color with some opacity
				stroke_width=stroke_width,
				stroke_color=stroke_color,
				background_color=bg_color,
				background_image=Image.open(visual_guide_upload),
				update_streamlit=realtime_update,
				height=canvas_height,
    			width=canvas_width,
				drawing_mode=drawing_mode,
				point_display_radius=point_display_radius if drawing_mode == 'point' else 0,
				key="canvas",
			)

			if canvas_result.image_data is not None:
				img2 = Image.fromarray(canvas_result.image_data) # Save the canvas drawing which is an Array as Image
			if visual_guide_upload:
				img1 = Image.open(visual_guide_upload)
				img1.paste(img2, (0,0), mask = img2) # superimpose drawing image img2 on the camera photo img1
				img1.save('canvas_image.png')
				byteImgIO = io.BytesIO()
				byteImg = Image.open("canvas_image.png")
				byteImg.save(byteImgIO, "PNG") # change the png image to IOBytes file
				byteImgIO.seek(0)
				canvas_image = byteImgIO.read()
			
			save_photo = st.button("Save edit",on_click=save_photo) # button to save the edit photo

			visual_guide_upload = st.session_state.visual_guide_upload 

		add_visual_button = st.button("Add media file as visual guide",on_click=add_visual_guide)	# Button to add the media file to the list of visual guides (st.file_uploader's on_change callback doesn't work for this unfortunately)

		# Section to create feedback/input fields for the users of the work instruction here
		# TD DO: Integrate with database/external processes (HTTP requests etc.)
		st.markdown("**(Optional) Add a field for user input**")
		input_type = st.selectbox("Type of input", ["--Choose an input type--","Text input","Button"])	# Dropdown list to choose the type of input

		if input_type == "Text input":	# For text input fields
			with st.form(key="input_form"):
				txtfield_name = st.text_input("Input field name")
				txtfield_destination = st.text_input("Destination key")			# Arbitrary placeholder, no function implemented yet
				txtfield_submit = st.form_submit_button("Create input field")	# Confirmation button to create the input field
				if txtfield_submit:
					st.session_state.step_list[st.session_state.step_index].step_inputs.append(TextField(txtfield_name,txtfield_destination))	# Create a Textfield() subclass of the Input() class object
		elif input_type == "Button":	# For buttons to trigger external processes
			with st.form(key="input_form"):
				button_name = st.text_input("Button name")
				button_function = st.selectbox("What does this button do?",["--Choose a function--","Send a message to admin","Trigger a process","Take a measurement"])	# Arbitrary placeholder, no function implemented yet
				button_submit = st.form_submit_button("Create button")			# Confirmation button to create the button
				if button_submit:
					st.session_state.step_list[st.session_state.step_index].step_inputs.append(Button(button_name,button_function))			# Create a Button() subclass of the Input() class object

		st.markdown("""---""") # divider line between editor section and preview section for clarity
		st.header("Preview")
		if step_title:
			st.subheader(str(st.session_state.step_index+1) + ". " + step_title)	# Display step number and step title to preview
		if (st.session_state.step_visual_list[st.session_state.step_index] != []):
			if len(st.session_state.step_visual_list[st.session_state.step_index]) == 1:	# For steps with only 1 visual guide item
				visual_cols = st.columns(2)	# Resize image/video to only half the page for organization
			else:
				visual_cols = st.columns(len(st.session_state.step_visual_list[st.session_state.step_index]))	# Otherwise, arrange all visual guide items in a row
			visual_index = 0
			for item in st.session_state.step_visual_list[st.session_state.step_index]:
				if 'image' in filetype.guess(item).mime:
					visual_cols[visual_index].image(item)	# Image files displayed through st.image widget
				elif 'video' in filetype.guess(item).mime:
					visual_cols[visual_index].video(item)	# Video files displayed through st.video widget
				else:
					visual_cols[visual_index].error("Could not display media file.")	# Error message
				visual_index+=1
		
		st.markdown(step_desc)	# Display description and detailed instructions of step

		input_list_length = len(st.session_state.step_list[st.session_state.step_index].step_inputs)
		input_list_index = range(input_list_length)		# Create list of indexes to select each Input() object
		input_preview_list = []
		if input_list_length > 0:
			for i in input_list_index:	# Create input field/button for each Input() object in the current step
				if st.session_state.step_list[st.session_state.step_index].step_inputs[i].input_type == 'text input':
					input_preview_list.append(st.text_input(st.session_state.step_list[st.session_state.step_index].step_inputs[i].input_name))
				elif st.session_state.step_list[st.session_state.step_index].step_inputs[i].input_type == 'button':
					input_preview_list.append(st.button(st.session_state.step_list[st.session_state.step_index].step_inputs[i].input_name))

		col1,col2,col3,col4,col5 = st.columns(5)	# Formatting to place button on the right side
		with col5:
			save_step_button = st.button("Save changes", on_click=save_wi,args=(st.session_state.wi_file_path,))	# Button to save work instruction to JSON file
	directory_button = st.button("Return to work instruction directory",on_click=return_to_directory)	# Button to return to main directory of all the work instructions


if st.session_state.page_mode == "deploy":	# Deploy mode: display the selected work instruction step-by-step for the reader to follow
	step_name_list = []
	step_select_list = []
	counter = 0

	for step in st.session_state.step_list:	# Import steps from session_state to deploy
		step_name_list.append(step.step_name)	# Create list of step titles
		counter += 1
		step_select_list.append("Step " + str(counter) + ": " + step.step_name)	# Display title and number of step

	if 'display_state' not in st.session_state:	# Initialize display_state variable which determines whether to show a step or the finish page
		st.session_state.display_state = 0		# In display_state == 0, step will be shown as normal

	if 'step_index' not in st.session_state:	# Initialize step_index variable to find the index of the step
		st.session_state.step_index = 0			# Start with the first step
	# next_step = False
	# finish_steps = False

	display_section = st.container()			# Declare container here to put in the finish page/step content

	if st.session_state.display_state == 1:		# display_state == 1, display finish page
		st.sidebar.markdown("Progress:")
		st.sidebar.progress(100)				# Atuomatically set progress bar to complete
		with display_section:
			st.title("Done!")
			st.markdown("Review the completed steps below:")
			for step_name in step_name_list:	# List the step titles as a summary to the user
				st.markdown("- " + step_name)
			confirm_complete_button = st.button("Confirm and return to main menu",on_click=return_to_directory)	# On
	else:
		st.sidebar.markdown("Progress:")
		st.sidebar.progress(float(st.session_state.step_index/len(step_name_list)))
		if st.session_state.step_index+1 < len(step_select_list):				# Shows next step if there are other steps left; otherwise, go to finish page
			next_step = st.button("Next step",on_click=next_publish)	# Button to go to the next step (increase step_index by 1)
		else:
			finish_steps = st.button("Finish",on_click=finish_publish)		# Button to return to main directory of all the work instructions
		with display_section:
			st.subheader(str(st.session_state.step_index+1) + ". " + st.session_state.step_list[st.session_state.step_index].step_name)	# Display step number and title
			if (st.session_state.step_visual_list[st.session_state.step_index] != []):
				if len(st.session_state.step_visual_list[st.session_state.step_index]) == 1:
					visual_cols = st.columns(2)	# Resize image/video to only half the page for organization
				else:
					visual_cols = st.columns(len(st.session_state.step_list[st.session_state.step_index].step_visual))	# Otherwise, arrange all visual guide items in a row
				visual_index = 0
				for item in st.session_state.step_visual_list[st.session_state.step_index]:
					if 'image' in filetype.guess(item).mime:
						visual_cols[visual_index].image(item)	# Image files displayed through st.image widget
					elif 'video' in filetype.guess(item).mime:
						visual_cols[visual_index].video(item)	# Video files displayed through st.video widget
					else:
						visual_cols[visual_index].error("Could not display media file.")	# Error message
					visual_index+=1
			
			# Display descriptions and detailed instructions of step and assign Display font size
			html_str = f"""
			<style>p.a {{font: bold {20}px Courier;}}</style>
			<p class="a">{st.session_state.step_list[st.session_state.step_index].step_desc}</p>
			"""
			st.markdown(html_str, unsafe_allow_html=True)

			# st.markdown(st.session_state.step_list[st.session_state.step_index].step_desc)	# Display descriptions and detailed instructions of step 

	step_select = st.sidebar.radio("Choose a step",step_select_list,key="step_select_radio",on_change=switch_step_deploy)	# Radio widget to switch to another step
