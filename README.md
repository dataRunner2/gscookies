## Introduction

## Inilize Elastic
Using the mappings jsons and the code in "admin_show_session" create the index template for each of the indices
Update the index names in Home.py file
for each index create an index

create elastic api key to put into Streamlit Secrets - upload .streamlit secrets.toml for local runs

## Launch Streamlit
Open terminal > 
activate the environment
source /Users/jennifer_home/Documents/08d_GSCookies/gscookies/.venv/bin/activate

if still not working:
poetry config virtualenvs.path
/Users/jennifer_home/Library/Caches/pypoetry/virtualenvspoetry config virtualenvs.in-project true
Forces the virtual environment into this project
poetry config virtualenvs.in-project true
poetry shell
source $(poetry env info --path)/bin/activate

Launch streamlit app

## TODO
Take the OpC out of the counts for # pending boxes
Add diagram to training page for process flows
fix booth orders page
fix manage orders page

