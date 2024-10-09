import torch
from rxnscribe import RxnScribe #need separate installation from https://github.com/thomas0809/RxnScribe 
from huggingface_hub import hf_hub_download
import cv2
import math
import numpy as np
import os
from openai import OpenAI
import base64
import requests
import json
from os import listdir
import json
import glob

#NOTE: Prompts stored locally for now but will store prompts used in the same repo folder in latest ver

class RxnOptDataProcessor:
    """
    Handles image processing tasks to extract reaction optimization-related data from images.
    """
    def __init__(self, ckpt_path, device='cpu'):
        self.api_key = os.getenv("OPENAI_API_KEY") # to use GPT
        self.model = RxnScribe(ckpt_path, device=torch.device(device)) # initialize RxnScribe to get SMILES

    def is_optimization_table(self, image_name, image_directory): 
        # filter logic from MERMES here 
        return True 
    
    def is_reaction_diagram(self, image_file):
        # logic to determine if the image is a reaction diagram
        return True    
    
    def crop_image(self, image_name, image_directory, cropped_image_directory, min_segment_height=120): 
        """
        Adaptively crop a given figure into smaller subfigures before passing to VLM based on image length

        parameters: 
        image_name: base image name
        image_directory: root directory where original images are saved 
        cropped_image_directory: output directory to save cropped images 
        min_segment_height: minimum height of each segmented subfigure
        """
        def find_split_line(image, threshold, region_start, region_end, percentage_threshold, step_size):
            """
            Helper function to determine where to segment the figure
            """
            
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) # Convert the image to grayscale            
            _, thresh = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY) # Identify white pixels
            white_pixel_count = np.count_nonzero(thresh == 255, axis=1) 

            # Find the last line with >= the specified percentage of white pixels in the specified region
            split_line = region_end
            while split_line > region_start:
                min_white_pixels = int(percentage_threshold * len(thresh[split_line]))

                if white_pixel_count[split_line] >= min_white_pixels:
                    break
                split_line -= step_size

            return split_line if split_line > region_start else region_start

        def adaptive_split_lines(image, first_split_line, min_segment_height, threshold, percentage_threshold, step_size):
            """
            Helper function to identify all the split lines for an image
            """
            
            # Calculate the remaining height after the first split line
            first_region_end = int(3/8 *len(image))
            remaining_height = image.shape[0] - first_region_end
            num_segments = math.ceil(remaining_height / min_segment_height)
            segment_height = remaining_height // num_segments  # Determine the approximate height of each segment

            split_lines = [first_split_line]  # Start with the first fixed split line
            region_start_list = [first_region_end] 

            for i in range(1, num_segments):
                # Calculate dynamic region start and end for each segment
                region_start = region_start_list[-1]
                region_end = region_start + segment_height
                region_start_list.append(region_end)

                # Find the split line for the current region
                split_line = find_split_line(image, threshold, region_start, region_end, percentage_threshold, step_size)
                split_lines.append(split_line)

            return split_lines
        
        def segment_image(image, split_lines):
            """
            Helper function to crop image based on split lines
            """
            segments = []
            prev_line = 0

            for split_line in split_lines:
                segments.append(image[prev_line:split_line, :])
                prev_line = split_line

            segments.append(image[prev_line:, :]) # Add the final segment (from the last split line to the end of the image)

            return segments
        
        image_path = os.path.join(image_directory, f"{image_name}.png")
        image = cv2.imread(image_path)

        if image is None:
            print(f"Error: Image {image_name}.png not found.")
            return
        
        # Set parameters
        threshold = 254.8
        percentage_threshold = 0.995
        step_size = 10

        # Find the first split line within the first 1/4 of the image (usually the reaction diagram)
        region_start_1 = int(1/4 * len(image))
        region_end_1 = int(3/8 *len(image))
        first_split_line = find_split_line(image, threshold, region_start_1, region_end_1, percentage_threshold, step_size)

        try: 
            # Find adaptive split lines based on the remaining height after the first split line
            split_lines = adaptive_split_lines(image, first_split_line, min_segment_height, threshold, percentage_threshold, step_size)

            # Check if split lines are valid
            if len(split_lines) < 1:
                raise ValueError(f"Error: Unable to find valid split lines for {image_name}. Saving original image.")

            # Crop the image into segments
            segments = segment_image(image, split_lines)

            # Check if cropped segments have valid size
            valid_segments = 0
            for idx, segment in enumerate(segments): 
                if segment.size > 0:
                    cv2.imwrite(os.path.join(cropped_image_directory, f"{image_name}_{idx+1}.png"), segment)
                    valid_segments += 1
                else: 
                    print(f"Warning: Segment {idx+1} of {image_name} has zero size. Skipping.")
            
            if valid_segments == 0:
                raise ValueError(f"Error: No valid segments for {image_name}. Saving original image.")

        except Exception as e: 
            print(str(e))
            cv2.imwrite(os.path.join(cropped_image_directory, f"{image_name}_original.png"), image)

    def batch_crop_image(self, input_directory, cropped_image_directory, min_segment_height=120):
        """
        crop all images in a given directory 
        """
        # Create a directory to save the cropped segments
        os.makedirs(cropped_image_directory, exist_ok=True)

        for file in os.listdir(input_directory):
            if (file.endswith('.png')):
                image_name = file.removesuffix('.png')
                print(f"processing {image_name}")
                self.crop_image(image_name, input_directory, cropped_image_directory, min_segment_height)
        print(f'All images cropped and saved in {cropped_image_directory}')

 
        """
        updates the reaction dictionary with footnote information 

        Additional parameters: 
        update_dict_prompt: prompt_name: file name of user message prompt to update reaction conditions
        json_file: saved response file for image_name using adaptive_get_data

        """
        response_path = os.path.join(json_directory, f"{json_file}_updated.json")
        token_path = os.path.join(f"{json_directory}/token_count/", f"{json_file}_updated_tokencount.json")

        # Read user message prompt
        user_prompt_path = os.path.join(prompt_directory, f"{update_dict_prompt}.txt")
        with open(user_prompt_path, "r") as file:
            user_message = file.read().strip()

        # Read json file    def encode_image(self, image_path): 
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def reformat_json(self, input_file):
        """
        Clean and format JSON data by removing unwanted characters and ensuring proper JSON formatting
        """
        with open(input_file, 'r') as file:
            json_content = file.read()
            json_content = json_content.replace("\"```json\\n", '').replace('```"', '').strip()       
            json_content = json_content.replace('\\n', '').replace('\\"', '"')
            data = json.loads(json_content)
            formatted_json = json.dumps(data, indent=4)

        # Write the formatted JSON to the output file
        with open(input_file, 'w') as file:
            file.write(formatted_json)

    def adaptive_get_data(self, prompt_directory, get_data_prompt, image_name, image_directory, json_directory):
        """
        Outputs a reaction dictionary from all subfigures 

        Parameters: 
        prompt_directory: directory path to user message prompt
        get_data_prompt: file name of user message prompt to get reaction conditions
        image_name: base image name 
        image_directory: root directory where the original images are stored
        json_directory: output directory to save all output json files 

        """
        # Get all subfigures files 
        image_paths = glob.glob(os.path.join(image_directory, f"{image_name}_*.png"))
        if not image_paths:
            print(f"No subimages found for {image_name}")
            return
    
        base64_images = [self.encode_image(image_path) for image_path in image_paths]

        # Get user prompt file
        user_prompt_path = os.path.join(prompt_directory, f"{get_data_prompt}.txt")
        with open(user_prompt_path, "r") as file:
            user_message = file.read().strip()

        # Get image captions and response file paths
        image_caption_path = os.path.join(image_directory, f"{image_name}.txt")
        response_path = os.path.join(json_directory, f"{image_name}_response.json")
        token_path = os.path.join(f"{json_directory}/token_count/", f"{image_name}_tokencount.json") # token count is saved in a subfolder in json_directory

        # Create base message
        messages = [{
            "role": "user",
            "content": [{"type": "text", "text": user_message}]
        }]

        # Add each encoded image as a separate entry
        messages[0]["content"].extend({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
        } for base64_image in base64_images)
        
        # If the image caption file exists, append it to the messages content
        if os.path.exists(image_caption_path):
            with open(image_caption_path, "r") as file:
                image_caption = file.read().strip()
            messages[0]["content"].append({"type": "text","text": image_caption})
            print('Caption appended!')
        else: 
            print('No caption found!')

        # API request headers and payload
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": "gpt-4o-2024-08-06",
            "messages": messages,
            "max_tokens": 4000
        }

        # Send API request
        try:
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            response.raise_for_status()  # Raise error if the request failed
            reaction_data = response.json()['choices'][0]['message']['content']
            token_count = response.json()['usage']

            # Save responses
            with open(response_path, 'w') as json_file:
                json.dump(reaction_data, json_file)
            print(f"Reaction data saved to {response_path}!")

            with open(token_path, 'w') as token_file: 
                json.dump(token_count, token_file)
            print(f"Token count saved to {response_path}!")

            # Clean response: 
            try: 
                self.reformat_json(response_path)
                print(f"{response_path}: Reaction data cleaned.")

            except Exception as e: 
                print(f"{response_path}: Reaction data not cleaned. Error: {e}")
        
        except requests.exceptions.RequestException as e:
            print(f"Error during API request: {e}")

    def update_dict(self, prompt_directory, update_dict_prompt, json_file, json_directory):
        
        # Get user prompt file
        user_prompt_path = os.path.join(prompt_directory, f"{update_dict_prompt}.txt")
        with open(user_prompt_path, "r") as file:
            user_message = file.read().strip()
        
        # Get Json file
        json_path = os.path.join(json_directory, f"{json_file}.json")
        with open(json_path, "r") as file2:
            json_dict = file2.read().strip()

        # Get response paths
        response_path = os.path.join(json_directory, f"{json_file}_updated.json")
        token_path = os.path.join(f"{json_directory}/token_count/", f"{json_file}_updated_tokencount.json")

        # Construct message
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": user_message
                    },
                    {
                        "type": "text",
                        "text": json_dict
                    }              
                ]
            }
        ]

        # API request headers and payload
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": "gpt-4o-2024-08-06",
            "messages": messages,
            "max_tokens": 4000
        }

        # Send API request
        try:
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            response.raise_for_status()  # Raise error if the request failed
            reaction_data = response.json()['choices'][0]['message']['content']
            token_count = response.json()['usage']

            # Save response
            with open(response_path, 'w') as json_file:
                json.dump(reaction_data, json_file)

            print(f"Reaction data saved to {response_path}!")

            with open(token_path,'w') as token_file:
               json.dump(token_count, token_file)

            print(f"Token count saved to {token_path}!")
            
            # Clean response
            try:
                self.reformat_json(response_path)
                print(f"{response_path}: Reaction data cleaned.")
            except Exception as e:
                print(f"{response_path}: Reaction data not cleaned.Error: {e}")
        
        except requests.exceptions.RequestException as e:
            print(f"Error during API request: {e}")

    # EDIT: Handle escape strings in smiles otherwise will have errors
    def extract_smiles(self, image_name, image_directory, json_directory):
        """
        Use RxnScribe to get reactants and product SMILES
        """
        ckpt_path = hf_hub_download("yujieq/RxnScribe", "pix2seq_reaction_full.ckpt")
        model = RxnScribe(ckpt_path, device=torch.device('cpu'))
        image_file = os.path.join(image_directory, f"{image_name}.png")
        reactions = []

        # Extract reactant and product SMILES
        if self.is_reaction_diagram(image_file):   
            try: 
                predictions = model.predict_image_file(image_file, molscribe=True, ocr=False)
            
                for prediction in predictions: 
                    #reactant_smiles = [reactant['smiles'] for reactant in prediction.get('reactants', [])]
                    #product_smiles = [product['smiles'] for product in prediction.get('products', [])]
                    reactant_smiles = [reactant.get('smiles') for reactant in prediction.get('reactants', []) if 'smiles' in reactant]
                    product_smiles = [product.get('smiles') for product in prediction.get('products', []) if 'smiles' in product]
                    reactions.append({'reactants': reactant_smiles, 'products': product_smiles})
            
            except Exception as e: 
                reactions.append({'reactants': ["N.R"], 'products': ["N.R"]})
            
            # Save SMILES list  
            smiles_path = os.path.join(json_directory, f"{image_name}_rxnsmiles.json")
            with open(smiles_path, 'w') as smiles_file: 
                json.dump(reactions, smiles_file)
        else:
            print(f"{image_name} is not a reaction diagram.")
    
    # EDIT: Handle NR SMILES dictionaries
    def update_dict_with_smiles(self, image_name, json_directory): 
        """
        Combine reaction dictionary with reaction SMILES
        """
        # load optimization runs dictionary 
        dict_path = os.path.join(json_directory, f"{image_name}_response_updated.json")
        with open(dict_path, "r") as file:
            opt_dict = json.load(file)
        opt_data = opt_dict["Optimization Runs"]

        # load reaction smiles list
        smiles_path = os.path.join(json_directory, f"{image_name}_rxnsmiles.json")
        with open(smiles_path, "r") as file2: 
            smiles_list = json.load(file2)
        
        if not smiles_list or 'NR' in smiles_list[0].get('reactants', '') or 'NR' in smiles_list[0].get('products', ''):
            reactants = 'NR' if not smiles_list or 'NR' in smiles_list[0].get('reactants', '') else smiles_list[0]['reactants']
            products = 'NR' if not smiles_list or 'NR' in smiles_list[0].get('products', '') else smiles_list[0]['products']
        else:
            reactants = smiles_list[0].get('reactants', 'NR')
            products = smiles_list[0].get('products', 'NR')

        # combine and save 
        updated_dict = {
            "SMILES": {
                "reactants": reactants, 
                "products": products
            }, 
            "Optimization Runs": opt_data
        }

        output_path = os.path.join(json_directory, f"{image_name}_full_opt_dictionary.json")
        with open(output_path, 'w') as output_file: 
            json.dump(updated_dict, output_file, indent = 4)

        print (f"Reaction optimization dictionary updated with reaction smiles for {image_name}")

    def batch_process_data(self, prompt_directory, get_data_prompt, update_dict_prompt, cropped_image_directory, json_directory, image_directory): 
        """
        Get the full reaction optimization dictionary for all images - reaction SMILES + reaction conditions        
        Should be able to streamline code further
        """
        # Extract reaction dictionary
        print('Extracting reaction dictionaries and reaction SMILES!')
        for file in os.listdir(image_directory):
            if (file.endswith(".png")):
                image_name = file.removesuffix('.png')
                print(f"processing {image_name}")
                self.extract_smiles(image_name, json_directory)
                self.adaptive_get_data(prompt_directory, get_data_prompt, image_name, cropped_image_directory, json_directory)
        
        # Update reaction dictionary with footnote information 
        print("Updating reaction dictionaries with footnote information!")
        for file in os.listdir(json_directory):
            if (file.endswith(".json")):
                json_name = file.removesuffix('.json')
                print(f"updating {json_name}")
                self.update_dict(prompt_directory, update_dict_prompt, json_name, json_directory)

        # Update reaction dictionary with reaction SMILES
        print("Updating reaction dictionaries with reaction SMILES!") 
        for file in os.listdir(json_directory): 
            if (file.endswith("_response_updated.json")):
                file_name = file.removesuffix("_response_updated.json")
                self.update_dict_with_smiles(self, file_name, json_directory)

        print("All reaction dictionaries are extracted and saved - hopefully")

           
        



# Testing 
ckpt_path = hf_hub_download("yujieq/RxnScribe", "pix2seq_reaction_full.ckpt") # Download the checkpoint
reaction_diagram = ReactionDiagram(ckpt_path, device='cpu') # Create an instance of the ReactionDiagram class
image_file = "/mnt/c/Users/Shi Xuan/OneDrive - University of Toronto/Project_MERLIN/Project_Optical reaction retrosynthesis/Test set/10.1021_acs.orglett.2c01930_figure3.jpeg" # Path to the image file
predictions = reaction_diagram.predict(image_file) 
if predictions:
    reaction_smiles = reaction_diagram.extract_smiles(predictions)
    print(reaction_smiles)

