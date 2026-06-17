import logging
import sys


from phl.agent import get_model
from phl.telegram import get_app

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s : %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    level=logging.INFO,
)


def main():
    model = get_model()
    telegram_app = get_app(model)

    telegram_app.run_polling()


if __name__ == "__main__":
    main()
