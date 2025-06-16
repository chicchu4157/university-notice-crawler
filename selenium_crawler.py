from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def crawl_dynamic_site(url):
    options = Options()
    options.add_argument('--headless')  # 백그라운드 실행
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    
    driver.get(url)
    # JavaScript 실행 대기
    driver.implicitly_wait(10)
    
    # 이제 driver.page_source로 HTML 가져오기
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    driver.quit()
    
    return soup
