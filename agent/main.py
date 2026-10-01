"""Start the student agent HTTP service."""

import os
import uvicorn
from agent.api import app


def main():
    uvicorn.run(app, host=os.getenv('HTTP_HOST', '127.0.0.1'),
                port=int(os.getenv('HTTP_PORT', '8001')))


if __name__ == '__main__':
    main()
