"""
زحف يومي شامل: السوق المفتوح + OLX لبنان
الاستخدام: python scrape_all.py
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import scraper_opensooq
import scraper_olx


def main():
    print("=== السوق المفتوح ===")
    scraper_opensooq.main()
    print("\n=== OLX لبنان ===")
    scraper_olx.main()


if __name__ == "__main__":
    main()
