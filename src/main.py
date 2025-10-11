from . import config, logging

def main():
    logging.set_up_logging("rsdb-map") # Set up logging

    conf = config.read_config() # Read config
    logging.set_logging_config(conf) # Set logging config

if __name__ == "__main__":
    main()
