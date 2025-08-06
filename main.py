import os
import time
import logging
from argparse import ArgumentParser
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from tqdm import tqdm
import requests

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('discord_image_downloader.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def setup_driver(profile_path: str, headless: bool = False):
    """Configura il driver Chrome con logging dettagliato"""
    try:
        abs_profile_path = os.path.abspath(os.path.expanduser(profile_path))
        logger.info(f"Configurando Chrome con profilo: {abs_profile_path}")
        
        if not os.path.exists(abs_profile_path):
            raise FileNotFoundError(f"Cartella del profilo non trovata: {abs_profile_path}")

        opts = Options()
        opts.add_argument(f"--user-data-dir={abs_profile_path}")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        
        if headless:
            logger.info("Modalità headless attivata")
            opts.add_argument("--headless=new")
            opts.add_argument("--disable-gpu")

        driver = webdriver.Chrome(options=opts)
        logger.info("ChromeDriver inizializzato con successo")
        return driver
        
    except Exception as e:
        logger.error(f"Errore durante l'inizializzazione del driver: {str(e)}")
        raise

def scroll_to_bottom(driver, max_scrolls: int = 50, pause: float = 1.0, timeout: int = 30):
    """Scrolla la pagina fino in fondo con logging dettagliato"""
    logger.info(f"Inizio scrolling (max {max_scrolls} scrolls, timeout {timeout}s)")
    last_height = driver.execute_script("return document.body.scrollHeight")
    start_time = time.time()
    scroll_attempts = 0
    
    while scroll_attempts < max_scrolls:
        scroll_attempts += 1
        logger.debug(f"Tentativo di scroll #{scroll_attempts}")
        
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause)
        
        new_height = driver.execute_script("return document.body.scrollHeight")
        logger.debug(f"Altezza precedente: {last_height}, nuova altezza: {new_height}")
        
        if new_height == last_height:
            if time.time() - start_time > timeout:
                logger.info(f"Timeout raggiunto dopo {timeout} secondi")
                break
            logger.debug("Nessun cambiamento nell'altezza, attesa prolungata")
            time.sleep(pause * 2)
            continue
            
        last_height = new_height
        
        try:
            if driver.find_elements(By.CSS_SELECTOR, "[class*='noMoreMessages']"):
                logger.info("Trovato indicatore di fine messaggi")
                break
        except Exception as e:
            logger.debug(f"Errore cercando indicatore fine messaggi: {str(e)}")
    
    logger.info(f"Scrolling completato dopo {scroll_attempts} tentativi")

def download_images(driver, output_dir: str):
    """Scarica le immagini con logging e gestione errori"""
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Download immagini nella cartella: {output_dir}")
    
    try:
        imgs = driver.find_elements(By.CSS_SELECTOR, "a[href*='cdn.discordapp.com']")
        logger.info(f"Trovate {len(imgs)} immagini potenziali")
    except Exception as e:
        logger.error(f"Errore cercando immagini: {str(e)}")
        return

    seen = set()
    downloaded = 0
    skipped = 0
    errors = 0

    for img in tqdm(imgs, desc="Download immagini"):
        try:
            url = img.get_attribute("href")
            if not url or url in seen:
                skipped += 1
                continue
                
            seen.add(url)
            logger.debug(f"Processo URL: {url}")
            
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            
            name = os.path.basename(url.split("?")[0])
            path = os.path.join(output_dir, name)
            
            with open(path, "wb") as f:
                f.write(resp.content)
            downloaded += 1
            logger.debug(f"Scaricato: {name}")
            
        except requests.exceptions.RequestException as e:
            errors += 1
            logger.warning(f"Errore download {url}: {str(e)}")
        except Exception as e:
            errors += 1
            logger.error(f"Errore imprevisto con {url}: {str(e)}")
    
    logger.info(f"Risultati download: {downloaded} scaricati, {skipped} saltati, {errors} errori")

def main():
    parser = ArgumentParser(description="Scarica immagini da un canale Discord")
    parser.add_argument("--profile", required=True,
                       help="Percorso alla cartella del profilo Chrome")
    parser.add_argument("--server-id", required=True, help="ID del server")
    parser.add_argument("--channel-id", required=True, help="ID del canale")
    parser.add_argument("--output", default="images", help="Cartella di destinazione")
    parser.add_argument("--scrolls", type=int, default=50,
                       help="Numero di scroll per caricare i messaggi")
    parser.add_argument("--pause", type=float, default=2.0,
                       help="Pausa (s) dopo ogni scroll")
    parser.add_argument("--headless", action="store_true", help="Esegui in background")
    parser.add_argument("--debug", action="store_true", help="Abilita logging dettagliato")
    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging abilitato")

    try:
        url = f"https://discord.com/channels/{args.server_id}/{args.channel_id}"
        logger.info(f"Accesso a: {url}")
        
        driver = setup_driver(args.profile, args.headless)
        driver.get(url)
        logger.info("Pagina caricata, attendo 5 secondi per il login...")
        time.sleep(5)

        scroll_to_bottom(driver, args.scrolls, args.pause)
        download_images(driver, args.output)

        logger.info("Operazione completata con successo")
    except Exception as e:
        logger.error(f"Errore durante l'esecuzione: {str(e)}")
    finally:
        if 'driver' in locals():
            driver.quit()
            logger.info("Browser chiuso")

if __name__ == "__main__":
    main()