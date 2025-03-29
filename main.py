import os
import time
import logging
import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from dotenv import load_dotenv
import openai

# ---------------------------
# Set up logging for debugging
# ---------------------------
if not os.path.exists("logs"):
    os.makedirs("logs")
log_filename = os.path.join("logs", f"debug_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)

def capture_screenshot(driver, name):
    """Capture a screenshot and save it to the 'screenshots' folder."""
    if not os.path.exists("screenshots"):
        os.makedirs("screenshots")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join("screenshots", f"{name}_{timestamp}.png")
    driver.save_screenshot(filename)
    logging.info(f"Screenshot saved: {filename}")

# ---------------------------
# Overlay Functions
# ---------------------------
def inject_overlay(text=""):
    """Inject a full-screen overlay with an initial status message."""
    driver.execute_script("""
    if (!document.getElementById('ai-overlay')) {
        var overlay = document.createElement('div');
        overlay.id = 'ai-overlay';
        overlay.style.position = 'fixed';
        overlay.style.top = '0';
        overlay.style.left = '0';
        overlay.style.width = '100%';
        overlay.style.height = '100%';
        overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
        overlay.style.color = 'white';
        overlay.style.fontSize = '24px';
        overlay.style.display = 'flex';
        overlay.style.alignItems = 'center';
        overlay.style.justifyContent = 'center';
        overlay.style.zIndex = '9999';
        overlay.style.pointerEvents = 'none';
        document.body.appendChild(overlay);
    }
    """)
    update_overlay(text)

def update_overlay(text):
    """Update the overlay text."""
    driver.execute_script(f"""
    var overlay = document.getElementById('ai-overlay');
    if (overlay) {{
        overlay.innerHTML = "<div style='background: rgba(0,0,0,0.7); padding: 10px; border-radius: 5px;'>{text}</div>";
    }}
    """)

def remove_overlay():
    """Remove the overlay from the page."""
    driver.execute_script("""
    var overlay = document.getElementById('ai-overlay');
    if (overlay) {
        overlay.parentNode.removeChild(overlay);
    }
    """)

def scroll_page(pixels, overlay_text="Scrolling..."):
    """Scroll the page by the given number of pixels and update the overlay."""
    update_overlay(overlay_text)
    driver.execute_script(f"window.scrollBy(0, {pixels});")
    time.sleep(2)
    capture_screenshot(driver, "after_scroll")

# ---------------------------
# Load API key from environment variables
# ---------------------------
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    logging.error("OpenAI API key not found. Please set it in the .env file.")
    exit(1)

# ---------------------------
# Initialize Selenium WebDriver
# ---------------------------
options = Options()
# For debugging, ensure the browser is visible (remove or comment out headless)
# options.add_argument("--headless")
driver = webdriver.Chrome(options=options)
driver.maximize_window()  # Maximize window for better visibility

def highlight(element, color='red'):
    """Highlight a Selenium WebElement with a colored border for debugging."""
    driver.execute_script(f"arguments[0].style.border='3px solid {color}'", element)
    logging.debug(f"Element highlighted with color {color}.")

try:
    # Step 1: Open the survey page and inject overlay
    url = "https://www.ihdresearch.com/?cid=ddaf9592-e094-48e5-921e-3832003ba9ca&language=en"  # Replace with your actual survey URL
    logging.info(f"Navigating to URL: {url}")
    driver.get(url)
    time.sleep(3)
    capture_screenshot(driver, "page_loaded")
    inject_overlay("Page Loaded")
    
    # Optionally, scroll down if content is below the fold
    scroll_page(300, "Scrolling down to load content...")

    # Step 2: Retrieve the full rendered HTML from the live DOM
    # This is equivalent to what you'd see in the Chrome DevTools Elements tab.
    rendered_html = driver.execute_script("return document.documentElement.outerHTML;")
    logging.info("Rendered HTML retrieved from live DOM.")
    update_overlay("Rendered HTML extracted")
    capture_screenshot(driver, "rendered_html_retrieved")
    time.sleep(2)

    # Step 3: Locate and extract the survey question and answer options
    # Adjust the selectors as needed. For this example, assume the question is in a <p> with class "survey-question".
    question_element = driver.find_element(By.CSS_SELECTOR, "p.survey-question")
    question_text = question_element.text.strip()
    highlight(question_element, color='orange')
    logging.info(f"Survey Question: {question_text}")
    capture_screenshot(driver, "question_highlighted")
    time.sleep(2)

    option_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='radio']")
    options_list = []
    for radio_input in option_inputs:
        radio_id = radio_input.get_attribute("id")
        if radio_id:
            try:
                label_element = driver.find_element(By.CSS_SELECTOR, f"label[for='{radio_id}']")
                option_text = label_element.text.strip()
            except Exception as e:
                logging.warning(f"Label for radio ID {radio_id} not found: {e}")
                option_text = "(no label)"
        else:
            option_text = "(no id/label)"
        options_list.append((radio_input, option_text))
    
    for idx, (radio_input, text) in enumerate(options_list, start=1):
        logging.info(f"Option {idx}: {text}")
        highlight(radio_input, color='blue')
        capture_screenshot(driver, f"option_{idx}_highlighted")
        time.sleep(1)
    
    # Step 4: Prepare prompt for OpenAI using the rendered HTML plus survey details.
    prompt = f"""
You are an AI with a custom personality designed to solve surveys.
Note that you do not have access to the raw page source; you only see the live rendered HTML.
Below is the rendered HTML of the page (as seen in the Chrome Elements panel):
{rendered_html}

Additionally, here is the survey question and its available answer options:
Survey Question: {question_text}
Options: {', '.join([txt for (_, txt) in options_list])}

Respond with the exact text of the option you would choose.
"""
    logging.info("Sending prompt to OpenAI.")
    logging.debug(f"Prompt: {prompt}")
    update_overlay("Processing Survey Question...")
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a survey-solving AI with a custom personality."},
            {"role": "user", "content": prompt}
        ]
    )
    chosen_option = response['choices'][0]['message']['content'].strip()
    logging.info(f"AI Chose: {chosen_option}")
    update_overlay(f"AI Chose: {chosen_option}")
    capture_screenshot(driver, "ai_choice_received")
    time.sleep(2)
    
    # Step 5: Match the AI's chosen option to one of the radio inputs and click it
    found = False
    for (radio_input, text) in options_list:
        if text == chosen_option:
            highlight(radio_input, color='green')
            capture_screenshot(driver, "chosen_option_highlighted")
            radio_input.click()
            logging.info("Clicked on the chosen option.")
            found = True
            break
    
    if not found:
        logging.warning("AI's chosen option was not found among the available options.")
        update_overlay("Chosen option not found!")
    
    # Step 6 (Optional): Click the "Next" button
    try:
        next_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Next')]")
        highlight(next_button, color='purple')
        capture_screenshot(driver, "next_button_highlighted")
        update_overlay("Clicking Next...")
        next_button.click()
        logging.info("Clicked the Next button.")
    except Exception as e:
        logging.warning(f"Could not find the Next button: {e}")
        update_overlay("Next button not found!")
    
    time.sleep(3)
    capture_screenshot(driver, "final_state")
    update_overlay("Process Completed")

except Exception as e:
    logging.exception("An error occurred during execution:")
    update_overlay("An error occurred!")
    time.sleep(3)
finally:
    logging.info("Closing browser...")
    driver.quit()
