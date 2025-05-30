import json
import os
import regex as re
from .processor_info import DataRaiderInfo
from . import postprocess as pp
from pathlib import Path

"""
Scripts for reaction dictionary formatting
"""

def reformat_json(input_file:str):
    """
    Clean and format JSON data by removing unwanted characters and 
    ensuring proper JSON formatting
    
    :param input_file: JSON file to reformat
    :type input_file: str
    
    :return: Returns nothing
    :rtype: None
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

    
def update_dict_with_smiles_old(
                    info:DataRaiderInfo,
                    image_name:str, 
                    image_directory:str, 
                    json_directory:str):
    """
    Use RxnScribe to get reactants and product SMILES and combine reaction dictionary with reaction SMILES
    
    :param info: Global information required for processing
    :type info: DataRaiderInfo
    :param image_name: Name of image
    :type image_name: str
    :param image_directory: Root directory where the original images are stored
    :type image_directory: str
    :param json_directory: Path to directory of reaction dictionary
    :type json_directory: str
    
    :return: Returns nothing, all data saved in JSON
    :rtype: None
    """
    image_file = os.path.join(image_directory, f"/cropped_images/{image_name}_1.png")
    if not os.path.exists(image_file):
        image_file = os.path.join(image_directory, f"/cropped_images/{image_name}_original.png")    
    reactions = []

    # Extract reactant and product SMILES
    try: 
        predictions = info.model.predict_image_file(image_file, molscribe=True, ocr=False)
        for prediction in predictions: 
            reactant_smiles = [reactant.get('smiles') for reactant in prediction.get('reactants', []) if 'smiles' in reactant]
            product_smiles = [product.get('smiles') for product in prediction.get('products', []) if 'smiles' in product]
            reactions.append({'reactants': reactant_smiles, 'products': product_smiles})
    
    except Exception as e: 
        reactions.append({'reactants': ["N.R"], 'products': ["N.R"]})
        print("No reaction SMILES extracted. Returning 'NR' for reactants and products.")
    
    #Clean extracted cleaned reaction SMILES 
    if not reactions or 'NR' in reactions[0].get('reactants', '') or 'NR' in reactions[0].get('products', ''):
        reactants = 'NR' if not reactions or 'NR' in reactions[0].get('reactants', '') else reactions[0]['reactants']
        products = 'NR' if not reactions or 'NR' in reactions[0].get('products', '') else reactions[0]['products']
    else:
        reactants = reactions[0].get('reactants', 'NR')
        products = reactions[0].get('products', 'NR')

    # Update reaction dictionary with reaction SMILES 
    json_path = os.path.join(json_directory, f"{image_name}.json")
    with open(json_path, 'r') as file: 
        opt_dict = json.load(file)
    opt_data = opt_dict["Optimization Runs"]
    if not opt_data:
        opt_data = opt_dict["Optimization Runs Dictionary"]

    updated_dict = {
        "SMILES": {
            "reactants": reactants, 
            "products": products
        }, 
        "Optimization Runs": opt_data
    }
    output_path = json_path # update the original json file
    with open(output_path, 'w') as output_file: 
        json.dump(updated_dict, output_file, indent = 4)
    print(f'{image_name} reaction dictionary updated with reaction SMILES')
    

def update_dict_with_smiles(
                    info:DataRaiderInfo,
                    image_name:str, 
                    image_directory:str, 
                    json_directory:str):
    """
    Use RxnScribe to get reactants and product SMILES and combine reaction dictionary with reaction SMILES
    
    :param info: Global information required for processing
    :type info: DataRaiderInfo
    :param image_name: Name of image
    :type image_name: str
    :param image_directory: Root directory where the original images are stored
    :type image_directory: str
    :param json_directory: Path to directory of reaction dictionary
    :type json_directory: str
    
    :return: Returns nothing, all data saved in JSON
    :rtype: None
    """
    image_directory = Path(image_directory)
    json_directory = Path(json_directory)

    image_file = image_directory / "cropped_images" / f"{image_name}_1.png"
    if not image_file.exists():
        image_file = image_directory / "cropped_images" / f"{image_name}_original.png"    
    reactions = []

    # Extract reactant and product SMILES
    try: 
        predictions = info.model.predict_image_file(image_file, molscribe=True, ocr=False)
        for prediction in predictions: 
            reactant_smiles = [reactant.get('smiles') for reactant in prediction.get('reactants', []) if 'smiles' in reactant]
            product_smiles = [product.get('smiles') for product in prediction.get('products', []) if 'smiles' in product]
            reactions.append({'reactants': reactant_smiles, 'products': product_smiles})
        
        if not reactions or not reactions[0]['reactants'] or not reactions[0]['products']:
            reactants, products = 'N.R', 'N.R'
        else: 
            reactants = reactions[0]['reactants']
            products = reactions[0]['products']
    
    except Exception as e: 
        print("No reaction SMILES extracted. Returning 'NR' for reactants and products.")
        reactants, products = 'N.R', 'N.R'

    # Update reaction dictionary with reaction SMILES 
    json_path = json_directory / f"{image_name}.json"
    # json_path = json_directory / f"{image_name}_updated.json" #retrieve updated if saved as new file
    with open(json_path, 'r') as file: 
        opt_dict = json.load(file)
    opt_key = next((k for k in opt_dict if "optimization" in k.lower()), None)
    if opt_key is None:
        print(f"WARNING. No optimization key found in the dictionary. Reactant and product SMILES not added")
        return
    opt_data = opt_dict[opt_key]

    updated_dict = {
        "SMILES": {
            "reactants": reactants, 
            "products": products
        }, 
        "Optimization Runs": opt_data
    }
    output_path = json_path # update the original json file
    # output_path = json_directory / f"{image_name}_updated_smiles.json" #save as new file
    with open(output_path, 'w') as output_file: 
        json.dump(updated_dict, output_file, indent = 4)
    print(f'{image_name} reaction dictionary updated with reaction SMILES')


def postprocess_dict(
                     image_name:str,
                     json_directory:str):
    """ 
    Converts common chemical names to smiles using pubchem and user-defined dictionary
    Unifies format for mixed solvent systems
    
    :param image_name: Name of image
    :type image_name: str
    :param json_directory: Path to directory of reaction dictionary
    :type json_directory: str
    """
    pp._process_raw_dict(image_name, json_directory, keys=pp.KEYS, common_names=pp.COMMON_NAMES)
    print("Postprocessing complete")


def construct_initial_prompt(
                            prompt_directory: str, 
                            opt_run_keys: list, 
                            new_run_keys: dict):
    """Creates a get_data_prompt with opt_run_keys key-value pairs embedded into it
    Uses <INSERT_HERE> as the location tag for inserting keys.
    Saves the new prompt to a file named get_data_prompt.txt inside the Prompts directory

    :param prompt_directory: Path to the prompt directory
    :type prompt_directory: str
    :param opt_run_keys: Optimization keys that are pre defined
    :type opt_run_keys: list
    :param new_run_keys: New optimization keys that are user defined
    :type new_run_keys: dict
    
    :return: Returns nothing, all data saved in txt file
    :rtype: None
    """
    prompt_directory = Path(prompt_directory)
    marker = "<INSERT_HERE>"

    # Retrieve all inbuilt keys
    inbuilt_key_pair_file_path = prompt_directory /"inbuilt_keyvaluepairs.txt"
    with open(inbuilt_key_pair_file_path, "r") as inbuilt_file:
        inbuilt_key_pair_file_contents = inbuilt_file.readlines()
    
    # Get the list of optimization run dictionary key value pairs
    opt_run_list = [f'"{key}": "{new_run_keys[key]}"\n' for key in new_run_keys]
    for line in inbuilt_key_pair_file_contents:
        if not line.strip():
            continue
        key_pattern = r'"([^"]*)"'
        possible_keys = re.findall(key_pattern, line)
        if not possible_keys:
            continue
        if all(key not in opt_run_keys for key in possible_keys):
            continue
        opt_run_list.append(line)
    
    base_prompt_file_path = prompt_directory / "base_prompt.txt"
    with open(base_prompt_file_path, "r") as base_prompt_file:
        base_prompt_file_contents = base_prompt_file.readlines()

    new_prompt_file_contents = []
    for line in base_prompt_file_contents:
        if marker in line: 
            new_prompt_file_contents.extend(opt_run_list)
        else: 
            new_prompt_file_contents.append(line)
    
    # Save the defined prompt as get_data_prompt
    new_prompt_file_path = prompt_directory / "get_data_prompt.txt"
    with open(new_prompt_file_path, "w") as new_prompt_file:
        new_prompt_file.writelines(new_prompt_file_contents)