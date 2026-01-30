from app.services.iherb_scraper import IHerbScraper, Product

class IHerbProductParser:
    def __init__(self):
        self.scraper = IHerbScraper()
    
    def parse_product(self, url: str) -> Product | None:
        return self.scraper.parse_product_page(url)
