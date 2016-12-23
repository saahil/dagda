import pymongo
import datetime
import configparser


class MongoDbDriver:

    # -- Public methods

    # MongoDbDriver Constructor
    def __init__(self):
        super(MongoDbDriver, self).__init__()
        self.__config = ConfigParser()
        self.client = pymongo.MongoClient('mongodb://' + self.__config.get_mongodb_host() + ':' +
                                          self.__config.get_mongodb_port() + '/')
        self.db = self.client.vuln_database

    # -- Inserting and bulk inserting methods

    # Bulk insert the cve list with the next format: <CVE-ID>#<vendor>#<product>#<version>
    def bulk_insert_cves(self, cve_list):
        products = []
        for product in cve_list:
            splitted_product = product.split("#")
            data = {}
            data['cve_id'] = splitted_product[0]
            data['vendor'] = splitted_product[1]
            data['product'] = splitted_product[2]
            data['version'] = splitted_product[3]
            data['year'] = int(splitted_product[4])
            products.append(data)
        # Bulk insert
        self.db.cve.create_index([('product', pymongo.DESCENDING)])
        self.db.cve.insert_many(products)

    # Bulk insert the bid list with the next format: <BID-ID>#<product>#<version>
    def bulk_insert_bids(self, bid_list):
        products = []
        for product in bid_list:
            splitted_product = product.split("#")
            data = {}
            data['bugtraq_id'] = int(splitted_product[0])
            data['product'] = splitted_product[1]
            data['version'] = splitted_product[2]
            products.append(data)
        # Bulk insert
        self.db.bid.create_index([('product', 'text')], default_language='none')
        self.db.bid.insert_many(products)

    # Bulk insert the exploit_db list with the next format: <EXPLOIT_DB-ID>#<product>#<version>
    def bulk_insert_exploit_db_ids(self, exploit_db_list):
        products = []
        for product in exploit_db_list:
            splitted_product = product.split("#")
            data = {}
            data['exploit_db_id'] = int(splitted_product[0])
            data['product'] = splitted_product[1]
            data['version'] = splitted_product[2]
            products.append(data)
        # Bulk insert
        self.db.exploit_db.create_index([('product', 'text')], default_language='none')
        self.db.exploit_db.insert_many(products)

    # Inserts the docker image scan result to history
    def insert_docker_image_scan_result_to_history(self, scan_result):
        if self.db.image_history.count() == 0:
            self.db.image_history.create_index([('image_name', pymongo.DESCENDING)])
        self.db.image_history.insert(scan_result)

    # -- Removing methods

    # Removes only the cves for updating and return the first year for inserting again
    def remove_only_cve_for_update(self):
        if "cve" not in self.db.collection_names() or self.db.cve.count() == 0:
            return 2002
        else:
            last_year_stored = self.db.cve.find({}, {'cve_id': 0, 'product': 0, 'version': 0, 'vendor': 0, '_id': 0})\
                                          .sort('year', pymongo.DESCENDING).limit(1)
            last_year = last_year_stored[0]['year'] - 1
            if last_year <= 2002:
                self.db.cve.drop()
                return 2002
            else:
                self.db.cve.remove({'year':{'$gte': last_year}})
                return last_year

    # Removes exploit_db collection
    def delete_exploit_db_collection(self):
        self.db.exploit_db.drop()

    # Removes bid collection
    def delete_bid_collection(self):
        self.db.bid.drop()

    # -- Querying methods

    # Gets the max bid inserted
    def get_max_bid_inserted(self):
        if "bid" not in self.db.collection_names() or self.db.bid.count() == 0:
            return 0
        else:
            last_bid = self.db.bid.find({}, {'product': 0, 'version': 0, '_id': 0})\
                                  .sort('bugtraq_id', pymongo.DESCENDING).limit(1)
            return last_bid[0]['bugtraq_id']

    # Gets the product vulnerabilities
    def get_vulnerabilities(self, product, version=None):
        filt_prod = product.replace("-", " ").replace("_", " ")
        if not version:
            # Gets CVEs
            cve_cursor = self.db.cve.find({'product': product}, {'product': 0, 'version': 0, '_id': 0})\
                                    .sort("cve_id", pymongo.ASCENDING)
            # Gets BugTraqs
            bid_cursor = self.db.bid.find({'$text': {'$search': filt_prod, '$language': 'none'}},
                                          {'product': 0, 'version': 0, '_id': 0})\
                                    .sort("bugtraq_id", pymongo.ASCENDING)
            # Gets Exploits
            exploit_db_cursor = self.db.exploit_db.find({'$text': {'$search': filt_prod, '$language': 'none'}},
                                                        {'product': 0, 'version': 0, '_id': 0})\
                                                  .sort("exploit_db_id", pymongo.ASCENDING)
        else:
            # Gets CVEs
            cve_cursor = self.db.cve.find({'product': product, 'version': version},
                                          {'product': 0, 'version': 0, '_id': 0})\
                                    .sort("cve_id", pymongo.ASCENDING)
            # Gets BugTraqs
            bid_cursor = self.db.bid.find({'$text': {'$search': filt_prod, '$language': 'none'}, 'version': version},
                                          {'product': 0, 'version': 0, '_id': 0})\
                                    .sort("bugtraq_id", pymongo.ASCENDING)
            # Gets Exploits
            exploit_db_cursor = self.db.exploit_db.find({'$text': {'$search': filt_prod, '$language': 'none'},
                                                         'version': version},
                                                        {'product': 0, 'version': 0, '_id': 0})\
                                                  .sort("exploit_db_id", pymongo.ASCENDING)
        # Prepare output
        output = []
        for cve in cve_cursor:
            if cve is not None:
                cve_temp = cve['cve_id']
                if cve_temp not in output:
                    output.append(cve_temp)
        for bid in bid_cursor:
            if bid is not None:
                bid_tmp = 'BID-' + str(bid['bugtraq_id'])
                if bid_tmp not in output:
                    output.append(bid_tmp)
        for exploit_db in exploit_db_cursor:
            if exploit_db is not None:
                exploit_db_tmp = 'EXPLOIT_DB_ID-' + str(exploit_db['exploit_db_id'])
                if exploit_db_tmp not in output:
                    output.append(exploit_db_tmp)
        # Return
        return output

    # Gets products by CVE
    def get_products_by_cve(self, cve):
        cursor = self.db.cve.find({'cve_id': cve}, {'cve_id': 0, '_id': 0}).sort([("product", pymongo.ASCENDING),
                                                                                  ("version", pymongo.ASCENDING)])
        # Prepare output
        output = []
        for product in cursor:
            if product is not None:
                output.append(product)
        # Return
        return output

    # Gets products by BID
    def get_products_by_bid(self, bid):
        cursor = self.db.bid.find({'bugtraq_id': bid}, {'bugtraq_id': 0, '_id': 0}).sort(
            [("product", pymongo.ASCENDING), ("version", pymongo.ASCENDING)])
        # Prepare output
        output = []
        for product in cursor:
            if product is not None:
                output.append(product)
        # Return
        return output

    # Gets products by Exploit_db id
    def get_products_by_exploit_db_id(self, exploit_db_id):
        cursor = self.db.exploit_db.find({'exploit_db_id': exploit_db_id}, {'exploit_db_id': 0, '_id': 0}).sort(
            [("product", pymongo.ASCENDING), ("version", pymongo.ASCENDING)])
        # Prepare output
        output = []
        for product in cursor:
            if product is not None:
                output.append(product)
        # Return
        return output

    # Gets docker image history
    def get_docker_image_history(self, image_name):
        cursor = self.db.image_history.find({'image_name': image_name}, {'_id': 0}).sort("timestamp",
                                                                                         pymongo.DESCENDING)
        # Prepare output
        output = []
        for scan in cursor:
            if scan is not None:
                scan['timestamp'] = str(datetime.datetime.utcfromtimestamp(scan['timestamp']))
                output.append(scan)
        # Return
        return output


class ConfigParser:

    # -- Public methods

    # ConfigParser Constructor
    def __init__(self):
        super(ConfigParser, self).__init__()
        self.config = configparser.ConfigParser()
        self.config.read('etc/checker.conf')

    # -- Getters

    # Get Mongodb host
    def get_mongodb_host(self):
        return self.config['MongoDB']['Host']

    # Get Mongodb port
    def get_mongodb_port(self):
        return self.config['MongoDB']['Port']
