#
# LibbyFetch - Download MP3 audiobooks from libbyapp.com
#
# Copyright (c) 2024 John Dalbey
#

# pip install selenium selenium-wire pycurl
# Note: must uninstall Blinker 1.9 and install v1.7
import time, os, pycurl, traceback
from selenium.common import TimeoutException
from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

#global variable for webdriver
driver = None

# Browse to the library page and perform the actions to login to libbyapp.com
def do_login_steps(driver):
    config_filename = "library_card_config.txt"
    try:
        print ("Reading library card configuration file.")
        library_config = []
        # Read library card configuration info: library code, card number, and PIN
        f = open(config_filename, 'r')
        library_config = f.readline().split(",")
        library_id = library_config[0].strip()
        library_cardnum = library_config[1].strip()
        library_pin = None
        # Check if a PIN parameter is included
        if len(library_config) == 3:
            library_pin = library_config[2].strip()

        print (f"Loading library page for '{library_id}'")
        driver.get(f"https://libbyapp.com/library/{library_id}")
        WebDriverWait(driver, 10)

        # Find the "Sign In" button by its class name and text content
        button_xpath = "//button[contains(@class, 'interview-answer-action') and contains(@class, 'halo') and .//span[@role='text' and (text()='Sign In With My Card' or text()='Try Again')]]"
        try: # Find the button using XPath
            button = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, button_xpath)))
            # Locate the prompt element
            span_element = driver.find_element(By.CSS_SELECTOR, '.interview-episode-say span')
            # Get the text from the span element
            span_text = span_element.text
            if span_text.endswith("details about this library."):
                print (f"Sorry, can't find details for library '{library_id}'")
                print ("Please confirm the library abbreviation and try again.")
                terminate()
            else:
                button.click()
                print("Starting signin with your library card.")
        except Exception as e:
            print(f"Unable to find 'Sign In With My Card' button.")
            terminate()

        # Find and fill the Card Number input field
        input_xpath = "//input[@class='shibui-form-input-control shibui-form-field-control' and @placeholder='card number']"
        try:  # Wait for the input field to be present
            input_field = WebDriverWait(driver, 10).until( EC.presence_of_element_located((By.XPATH, input_xpath)) )
            # Fill in the value
            input_field.send_keys(library_cardnum)
            time.sleep(1)
            input_field.send_keys(Keys.ENTER)
            print ("Library card number entered.")
            time.sleep(1)
        except Exception as e:
            print(f"An error occurred entering card number: {e}")
            terminate()

        # If the configuration has a PIN, enter it
        if library_pin is not None:
            # Find and fill the PIN input field
            input_id = "shibui-form-input-control-0002"
            try:  # Wait for the input field to be present
                input_field = WebDriverWait(driver, 10).until( EC.visibility_of_element_located((By.ID, input_id)) )
                # Fill in the value
                input_field.send_keys(library_pin)
                time.sleep(1)
                input_field.send_keys(Keys.ENTER)
                print("PIN entered.")
                time.sleep(1)
            except Exception as e:
                print(f"An error occurred filling PIN:")
                traceback.print_exc()
                terminate()

        # if no PIN continue here
        retry_count = 0
        signin_complete = False
        # Repeat until signin succeeds, or the retry count is exceeded
        while not signin_complete and retry_count <= 3:
            # "Next" button will appear at this point.
            button_xpath = "//button[contains(@class, 'interview-answer-action') and contains(@class, 'halo') and span[contains(@class, 'interview-answer-action-flex')] and .//span[@role='text']]"
            try: # Find the button using XPath
                button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, button_xpath)))
                # Locate the prompt element
                span_element = driver.find_element(By.CSS_SELECTOR, '.interview-episode-say span')
                # Get the text from the prompt element
                span_text = span_element.text
                # Determine which prompt appeared
                if span_text.startswith("Unfortunately"):
                    print("Card not verified, probably a Libby error, we will retry in a few seconds.")
                    retry_count += 1
                    time.sleep(5)
                    print ("Retrying...")
                    # Click "Try Again" to make the card number and pin fields reappear.
                    button.click()
                elif span_text.startswith("We could not verify your card"):
                    print (f"Sorry, your library card (or PIN) could not be verified.")
                    print(f"Please confirm these credentials and try again: {library_config}")
                    terminate()
                elif span_text.startswith("Enter"):
                    button.click()
                else:  #span_text.startswith("Okay")
                    button.click()
                    print("Sign In completed.")
                    signin_complete = True
            except Exception as e:
                print(f"Login seems to have failed. ")
                print (f"Please verify these credentials and retry: {library_config}")
                abnormal_exit(e)
        if retry_count > 3:
            print (f"Giving up after {retry_count} retries.")
            terminate()
    except FileNotFoundError:
        print(f"Missing or malformed configuration file: {config_filename}")
        terminate()
    except IndexError:
        print(f"Malformed configuration file: {config_filename}")
        terminate()
    except Exception as e:
        print (f"Login failed, sorry.")
        print (type(e))
        abnormal_exit(e)

# Display the list of book titles in 3 columns
# @param a list of DIV elements from the loans page, one for each book.
def display_in_columns(div_list):
    # Determine the number of rows needed
    rows = (len(div_list) + 2) // 3

    for i in range(rows):
        # Get the items for the current row
        row_items = []
        for j in range(3):
            index = i*3 + j
            if index < len(div_list):
                # Extract the text from the span with class "title-tile-title"
                title_text = div_list[index].find_element(By.CLASS_NAME, "title-tile-title").text
                # Preface the title with an index number
                brief_title = str(index+1) + ". " + title_text.strip()[:23]
                row_items.append(brief_title)
            else:
                row_items.append("")

        # Format the row items to be 26 characters wide
        formatted_row = f"{row_items[0]:<26} {row_items[1]:<26} {row_items[2]:<26}"
        # Print the formatted row
        print(formatted_row)

# Get the page elements for the books and display the titles
def list_titles(driver):
    # Find all title-tile divs
    book_divs = driver.find_elements(By.CLASS_NAME, "title-tile")
    # Check that books exist
    if len(book_divs) == 0:
        print ("\nIt appears you have no audiobooks on loan at this library.")
        print ("Nothing to download, quitting.")
        terminate()

    # Display the list in columns
    display_in_columns(book_divs)

# Open the audiobook
# @param list of book divs
# @param user's choice of an item in the list
def open_audiobook(book_divs, choice):
    try:
        if choice < 1:
            raise IndexError
        # Find the specific title-tile div based on user choice
        chosen_title = book_divs[choice - 1]
        # Find and click the "Open Audiobook" button within the chosen div
        open_button = chosen_title.find_element(By.XPATH, ".//button[span[text()='Open Audiobook']]")
        open_button.click()
        print("Opening Audiobook.")
    except IndexError:
        print("Sorry your choice is not in the list.")
        terminate()

# Display list of books and get user's selection
# @return a list of div elements for the books
# @return an integer the user chose from the list
def choose_book(driver):
    try:
        # Navigate to the page listing audiobooks on loan
        driver.get("http://libbyapp.com/shelf/loans/default,audiobook")

        try:
            # Wait for the <h1> Loan element
            # NB: Even after the H1 element is present it never becomes "visible".  There's a graphical fade-in
            # effect that is probably interfering.
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, "screen-shelf-collation-heading"))
            )

            # The following sleep() allows the animation to complete
            # at which time the audiobook titles can be viewed and accessed.
            # There may be a better way to achieve this than a hardcoded sleep.
            time.sleep(2)
            print("Loans page loaded.")
        except TimeoutException:
            print("Loans page seems to not have loaded.  Try again.")
            terminate()

        # List all titles and get the titles elements
        list_titles(driver)
        book_divs = driver.find_elements(By.CLASS_NAME, "title-tile")

        # Prompt the user to enter the number of the desired title
        choice = int(input("Enter the number of the desired title: "))
        return book_divs, choice
    except ValueError:
        print ("Choice must be a number. Quitting.")
        terminate()

# Obtain the URL for the desired book
# @param a list of divs for the books
# @param an integer representing the user's choice from the list
# @return the URL for the first MP3 of the audiobook
# @return list of cookies needed to fetch the URL
def obtain_book_url(book_divs, choice):
    try:
        # Open the audiobook for the chosen title
        open_audiobook(book_divs, choice)
        # This is the 'secret' that allows this script to do its magic
        # Once the audiobook is opened in the browser, libbyapp will use a GET request to obtain the MP3 file.
        # Our script will snoop on the network requests looking for a GET request with an URL that contains
        # a specific phrase that identifies the MP3 file.
        print ("Retrieving audiobook url...")
        magic_phrase = "Fmt425-Part"  # a unique phrase that identifies Libby's request for an MP3
        cookies = None
        book_url = ""
        while (cookies == None):
            time.sleep(2)
            print (f"waiting")
            for request in driver.requests:
                if request.method == "GET":
                    book_url = request.url
                    # Look for the request that has the MP3 name
                    if book_url.find(magic_phrase) > 0:
                        cookies = request.headers["cookie"]
                        break
        return book_url, cookies

    except Exception as e:
        print (f"Exception retrieving book")
        abnormal_exit(e)

# Initialize a variable to track the last reported percentage
last_reported_percent = -1

# Perform the cURL command needed to download one MP3 file
def do_pycurl_cmd(book_title, deweyURL, cookie):
    # Progress callback function to print only at multiples of 10%
    def progress(download_t, download_d, up_t, up_d):
        global last_reported_percent

        if download_t > 0:  # Only calculate percentage if total size is known
            percent = int((download_d / download_t) * 100)

            # Print progress if it is a multiple of 10 and hasn't been reported yet
            if percent % 10 == 0 and percent != last_reported_percent:
                print(f" {percent}% ", end='', flush=True)
                last_reported_percent = percent

    # Initialize pycURL object
    c = pycurl.Curl()
    # Set URL
    c.setopt(c.URL, deweyURL)

    # Follow redirects (equivalent to `-L`)
    c.setopt(c.FOLLOWLOCATION, True)

    # Set custom headers
    c.setopt(c.HTTPHEADER, [
        'User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0',
        'Accept: audio/webm,audio/ogg,audio/wav,audio/*;q=0.9,application/ogg;q=0.7,video/*;q=0.6,*/*;q=0.5',
        'Accept-Language: en-US,en;q=0.5',
        'Range: bytes=0-',
        'DNT: 1',
        'Connection: keep-alive',
        'Sec-Fetch-Dest: audio',
        'Sec-Fetch-Mode: cors',
        'Sec-Fetch-Site: same-origin',
        'Sec-GPC: 1',
        'Accept-Encoding: identity',
        'Priority: u=4',
        'TE: trailers'
    ])
    # Set cookies as a single string (format: "cookie1=value1; cookie2=value2")
    c.setopt(c.COOKIE, cookie)
    # Specify the path to your CA certificates bundle
    c.setopt(c.CAINFO, '/etc/ssl/certs/ca-certificates.crt')

    # Save the output retrieved by cURL to a file
    with open(book_title, 'wb') as f:
        c.setopt(c.WRITEDATA, f)
        # Set up the progress function callback
        c.setopt(c.XFERINFOFUNCTION, progress)
        c.setopt(c.NOPROGRESS, False)  # Enable the progress function
        print ("Download progress: ", end='')
        # Perform the request
        c.perform()
        print ()
        c.close()

# Fetch the MP3 files that comprise the audiobook
# @param title is the string representing the book (with blanks replaced by underscores)
# @param deweyURL is the book URL in form expected by libbyapp
# @param cookie the cookie string
# @result the MP3 files are downloaded into the current folder
def fetch_audio_files(title, deweyURL, cookie):
    audio_filename = title + "_Part01.mp3"
    filesize = 99
    part_counter = 1
    # Since we don't know in advance how many mp3 files comprises the audiobook
    # we just iterate fetching files until we get one with a size of 1 byte.
    while filesize > 1:
        # Rename the command with the current part number
        part_num = "Part" + f"{part_counter:02}"
        audio_filename = title + "_" + part_num + ".mp3"
        currentURL = deweyURL.replace("Part01",part_num)
        print (audio_filename)
        do_pycurl_cmd(audio_filename, currentURL, cookie)
        # Retrieve the filesize of the downloaded .mp3 file
        filesize = os.path.getsize(audio_filename)
        # increment the part number for the next iteration
        part_counter += 1

    print(f"Fetch completed.  {part_counter - 1} files downloaded.")
    # Delete the last file since it is only 1 byte long.
    print("Removing scrap file: ", audio_filename)
    try:
        os.remove(audio_filename)
    except FileNotFoundError:
        print("Failed to delete scrap file - probably programmer error")
        terminate()

def terminate():
    driver.quit()
    exit()

def abnormal_exit(e):
    print ("An error occurred for an unknown cause.")
    print ("Exception type: ",type(e))
    print (f"Message: {e}")
    traceback.print_exc()
    driver.quit()
    exit(-1)

# Entry point for the application
if __name__ == "__main__":
    try:
        # Initialize the WebDriver
        # Known Issue: Apparently there's a known issue with the Chrome webdriver. If the user manually minimizes
        # the browser window while the script is running it causes the driver to lose focus or fail to interact with
        # the page elements properly.  Firefox doesn't have this problem.  The workaround is to run in headless mode,
        # as shown below.
        print ("Initializing LibbyApp.")
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        options = ChromeOptions()
        options.add_argument("--headless")
        driver = webdriver.Chrome(options=options)
        do_login_steps(driver)
        # Get user's book choice
        book_divs, choice = choose_book(driver)
        book_name = book_divs[choice - 1].find_element(By.CLASS_NAME, "title-tile-title").text
        # Hunt down the URL of the book
        deweyURL, cookie = obtain_book_url(book_divs, choice)
        book_title = book_name.replace(" ", "_")
        # Go retrieve the MP3 files
        print (f"Ready to fetch audio book {book_name}.")
        fetch_audio_files(book_title, deweyURL, cookie)
        print ("That's all Folks!")
        driver.quit()
    except Exception as e:
        abnormal_exit(e)
