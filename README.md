# Metal Archives + MP3Tag Web Proxy 

## Disclaimer

Doing this project in Python was a little more than just an excuse to learn a new programming language (I'm more versed on C#/.NET), so there could be some details that will need to be polished that I could have missed during develpment and pre-release testing.

Please let me know, by creating a ticket, in case that something is not working as expected.

## Short Description

Proxy server written in Python to be used to get data from Metal Archives to be used by MP3Tag Web Sources.

## Dependencies

Due to how getting data from Metal Archives works, this proxy makes use of the following 3rd party components:

- **Playwright**: A framework for Web Testing and Automation.
- **Beautiful Soup**: A library for web-scrapping.

About Playwright... Well, I know that probably is a little bit an overkill, but being honest, due to the challenges faced to be able to get data from Metal Archives, this was the most convenient (and probably lightweight, and free) way to achieve it.

## Pre-requisites

To be able to run this proxy server Python 3.12.10 needs to be installed and can be downloaded from [Python offical site](https://www.python.org/downloads/release/python-31210/).

## Installation

**Disclaimer**: Please note that these instructions are based on a Windows 10 environment using Powershell, and they can and will vary when applied to other systems. I will update this readme them some time later to include them.

### Automatic (Windows only-ish)

To install all required components, and apply required configurations for this proxy, just run included Powershell Script `setup.ps1` on a Powershell terminal.

There are a number of ways to do this, but the easiest way, in my opinion, is to do right click on the file, and select "Run with PowerShell".

### Manual

Once donwloaded latest version of all file, open a Powershell terminal and navigate to scripts location, and follow these steps.

Also, please note that following commands will use the same names as `setup.ps1` script.

#### 1. Create Proxy's own virtual environment.

We need to create a virtual environment to have all dependencies in one place, and accessible only for this Proxy.

````
python -m venv ma_venv
````

#### 2. Activate created virtual environment

````
.\ma_venv\Scripts\Activate.ps1
````

#### 3. Install all required components

Note: This step can take a while to complete, as it needs to download and install all required libraries.

````
pip install -r requirements.txt
````

#### 4. Configuring and installing local web browser

This command is to configure browser used by Playwright as a local browser (i.e., accessible only by the Proxy)
````
$env:PLAYWRIGHT_BROWSERS_PATH = "0"
````

This is to actually download the browser and have it available by Proxy.

Please note that this step can take from a few seconds, to a couple of minutes to complete.

````
playwright install firefox
````

#### 5. (Optional) Deactivate virtual environemtn
Once previous steps are complete, you can either start using the Proxy straigh away (see second step in **Usage**), or to finish the process and make use of the Proxy in another time.

In either case, at the end of all the process we need to deactivate the virtual environment by typing

````
deactivate
````

And we can close PowerShell afterwards.

## Usage

To run the Proxy, open a Powershell terminal and navigate to scripts location, and follow next steps:

### 1. Activate virtual environment
````
.\ma_venv\Scripts\Activate.ps1
````
### 2. Start Proxy
````
python proxy_ma.py
````

Once Proxy stars it'll start showing various status messages, and will indicate when it is ready to be used.

To stop the server just close the PowerShell window, or press `Ctrl + C` on terminal to stop it.

## Integration with MP3Tag

As this Proxy will be used as a "middle-man" between MP3Tag and Metal Archives, some changes were needed to be done on scripts used by the former.

Also, as this proxy handles the web scrapping part instead MP3Tag, data for tagging is sent in a different way (JSON instead raw HTML).

As these changes are imcompatible with current versions of the scripts, I've added new versions of some of the scripts on this project, and can be found in the `MP3Tag_Scripts` folder.

Included scripts are:

* Band Info
* Search by Album
* Search by Band
* Search by Band + Album
* Search by URL

Additionally, a new script was added:

* Search by Band + Album (Full)

This script is one of the oldest request that I had in my queue/backlog since I started to maintain these scripts, and basically merges "Band Info" and "Search by Band + Album" scripts.

In the past this wasn't possible due to how MP3Tag works (bsically one explicit request at a time), but as now the Proxy handles those requests, that limitation is no more.

The only downside is that getting the data takes a little bit more than usual due to the multiple requests to Metal Archives.

I have plans to migrate the rest of the scripts to be compatible with the Proxy, but that mainly depends on if people finds this project useful.

## Cache

To be a nice Proxy (heh) and to prevent being flagged by Metal Archives, there's a cache implementation in this Proxy that stores the following information:

* Search Band + Album data.
* Search Band Info data.
* Album data.
* Band data.
* Band + Album (Full) data.

The cache implementation has the following characteristics:

* No additional components required, as all data will be stored in a local `ma_cache.db` file.
    * Additional files are created as backup.
    * All cache files can be deleted in any given moment without issues, as those will be recreated.
* Cache is configured to be renewed every 15 days.
    * This only applies to any given data that is older than 15 days.

## Credits

This project uses the following libraries/3rd party software:

* **Playwright** ([https://playwright.dev/](https://playwright.dev/))
* **Beautiful Soup** ([https://www.crummy.com/software/BeautifulSoup/](https://www.crummy.com/software/BeautifulSoup/))