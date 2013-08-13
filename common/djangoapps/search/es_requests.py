"""
General methods and classes for interaction with the Mongo Database and Elasticsearch instance
"""

import json
import os
import re
import urllib
import base64
import hashlib
import cStringIO
import StringIO
import logging
import socket

import requests
from requests.exceptions import RequestException
from django.conf import settings
from pymongo import MongoClient
from pdfminer.pdfinterp import PDFResourceManager, process_pdf
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfparser import PDFSyntaxError
from wand.image import Image
from wand.exceptions import DelegateError, MissingDelegateError, CorruptImageError  # pylint: disable=E0611
from xhtml2pdf import pisa as pisa
from xhtml2pdf.w3c.cssParser import CSSParseError

log = logging.getLogger("edx.search")
MONGO_COURSE_CACHE = {}


def flaky_request(method, url, **kwargs):
    """
    General exception handling for requests
    """
    request = getattr(requests, method)
    response = None
    attempts = kwargs.get("attempts", 2)
    for _ in range(attempts):
        try:
            response = request(url, **kwargs)
            break
        except RequestException:
            pass
    if response is None:
        return None
    else:
        return response


class ElasticDatabase:
    """
    A wrapper for Elastic Search that sits on top of the existent REST api.

    In a broad sense there are two layers in Elastic Search. The top level is
    an index. In this implementation indicies represent types of content (transcripts, problems, etc...).
    The second level, strictly below indicies, is a type.

    In this implementation types are hashed course ids (SHA1).

    In addition to those two levels of nesting, each individual piece of data has an id associated with it.
    Currently the id of each object is a SHA1 hash of its entire id field.

    Each index has "settings" associated with it. These are quite minimal, just specifying the number of
    nodes and shards the index is distributed across.

    Each type has a mapping associated with it. A mapping is essentially a database schema with some additional
    information surrounding search functionality, such as tokenizers and analyzers.

    Right now these settings are entirely specified through JSON in the settings.json file located within this
    directory. Most of the methods in this class serve to instantiate types and indices within the Elastic Search
    instance. Additionly there are methods for running basic queries and content indexing.
    """

    def __init__(self, settings_file=None):
        """
        Instantiates the ElasticDatabase file.

        This includes a url, which should point to the location of the elasticsearch server.
        The only other input here is the Elastic Search settings file, which is a JSON file
        that should be specified in the application settings file.
        """

        self.url = settings.ES_DATABASE
        if settings_file is None:
            current_directory = os.path.dirname(os.path.realpath(__file__))
            settings_file = os.path.join(current_directory, "settings.json")

        with open(settings_file) as source:
            self.index_settings = json.load(source)

    def index_data(self, index, data, type_, id_):
        """
        Actually indexes given data at the indicated type and id.

        If no type or id is provided, this will assume that the type and id are
        contained within the data object passed to the index_data function in the
        hash and type_hash fields.

        Data should be a dictionary that matches the mapping of the given type.
        """

        full_url = "/".join([self.url, index, type_, id_])
        return flaky_request("post", full_url, data=json.dumps(data))

    def bulk_index(self, all_data):
        """
        Allows for bulk indexing of properly formatted json strings.
        Example:
        {"index": {"_index": "transcript-index", "_type": "course_hash", "_id": "id_hash"}}
        {"field1": "value1"...}

        Important: Bulk indexing is newline delimited, make sure newlines are only
        between action (line starting with index) and data (line starting with field1)
        """

        url = self.url + "/_bulk"
        return flaky_request("post", url, data=all_data)

    def delete_index(self, index):
        """
        Deletes the index specified, along with all contained types and data
        """

        full_url = "/".join([self.url, index])
        return flaky_request("delete", full_url)


class MongoIndexer:
    """
    This class is the connection point between Mongo and ElasticSearch.
    """

    def __init__(
        self, host, port, content_database='xcontent', file_collection="fs.files",
        chunk_collection="fs.chunks", module_database='xmodule', module_collection='modulestore',
        es_instance=ElasticDatabase()
    ):
        self.host = host
        self.port = port
        self.client = MongoClient(host, port)
        self.content_db = self.client[content_database]
        self.module_db = self.client[module_database]
        self.file_collection = self.content_db[file_collection]
        self.chunk_collection = self.content_db[chunk_collection]
        self.module_collection = self.module_db[module_collection]
        self.es_instance = es_instance

    def find_asset_with_name(self, name):
        """
        Returns a single asset whose filename exactly matches the one provided
        """

        return self.chunk_collection.find_one({"files_id.category": "asset", "files_id.name": name}, timeout=False)

    def find_modules_for_course(self, course):
        """
        Returns a cursor matching all modules in the given course
        """

        return self.module_collection.find({"_id.course": course}, timeout=False)

    def find_transcript_for_video_module(self, video_module):
        """
        Returns a transcript for a video given the module that contains it.

        The video module should be passed in as an element from some mongo cursor.
        """

        data = video_module.get("definition", {"data": ""}).get("data", "")
        if isinstance(data, dict):  # For some reason there are nested versions
            data = data.get("data", "")
        if isinstance(data, unicode) is False:  # for example videos
            return [""]
        uuid = self.uuid_from_video_module(video_module)
        if uuid:
            name_pattern = re.compile(".*?" + uuid + ".*?")
        else:
            return [""]
        chunk = self.chunk_collection.find_one({"files_id.name": name_pattern})
        if chunk is None:
            return [""]
        elif "com.apple.quar" in chunk["data"].decode('utf-8', "ignore"):
            # This seemingly arbitrary error check brought to you by apple.
            # This is an obscure, barely documented occurance where apple broke tarballs
            # and decided to shove error messages into tar metadata which causes this.
            # https://discussions.apple.com/thread/3145071?start=0&tstart=0
            return [""]
        else:
            try:
                return " ".join(filter(None, json.loads(chunk["data"].decode('utf-8', "ignore"))["text"]))
            except ValueError:
                log.error("Transcript for: " + uuid + " is invalid")
                return chunk["data"].decode('utf-8', 'ignore')

    def pdf_to_text(self, mongo_element):
        """
        Returns human-readable text from a given pdf.

        The mongo element should be a member of fs.chunks, since this is expecting a binary
        representation of the pdf.

        It's worth noting that this method is relatively verbose, largely because mongo contains
        a number of invalid or semi-valid pdfs.
        """

        only_ascii = lambda s: "".join(c for c in s if ord(c) < 128)
        resource = PDFResourceManager()
        return_string = cStringIO.StringIO()
        params = LAParams()
        converter = TextConverter(resource, return_string, codec='utf-8', laparams=params)
        fake_file = StringIO.StringIO(mongo_element["data"].__str__())
        try:
            process_pdf(resource, converter, fake_file)
        except PDFSyntaxError:
            log.debug(mongo_element["files_id"]["name"] + " cannot be read, moving on.")
            return ""
        text_value = only_ascii(return_string.getvalue()).replace("\n", " ")
        return text_value

    def searchable_text_from_problem_data(self, mongo_element):
        """
        The data field from the problem is in weird xml, which is good for functionality, but bad for search
        """

        data = mongo_element["definition"]["data"]
        paragraphs = " ".join([text for text in re.findall(r"<p>(.*?)</p>", data) if text is not "Explanation"])
        paragraphs += " "
        paragraphs += " ".join([text for text in re.findall(r"<text>(.*?)</text>", data)])
        cleaned_text = re.sub(r"\\(.*?\\)", "", paragraphs).replace("\\", "")
        remove_tags = re.sub(r"<[a-zA-Z0-9/\.\= \"\'_-]+>", "", cleaned_text)
        remove_repetitions = re.sub(r"(.)\1{4,}", "", remove_tags)
        return remove_repetitions

    def thumbnail_from_video_module(self, video_module):
        """
        Return an appropriate binary thumbnail for a given video module
        """

        data = video_module.get("definition", {"data": ""}).get("data", "")
        if "player.youku.com" in data:
        # Some videos use the youku player, this is just the default youku icon
        # Youku requires an api key to pull down relevant thumbnails, but
        # if that is ever present this should be switched. Right now it only applies to two videos.
            url = "https://lh6.ggpht.com/8_h5j6hiFXdSl5atSJDf8bJBy85b3IlzNWeRzOqRurfNVI_oiEG-dB3C0vHRclOG8A=w170"
        else:
            uuid = self.uuid_from_video_module(video_module)
            if uuid is False:
                url = "http://img.youtube.com/vi/Tt9g2se1LcM/4.jpg"
            else:
                url = "http://img.youtube.com/vi/%s/0.jpg" % uuid
        return url

    def uuid_from_video_module(self, video_module):
        """
        Returns the youtube uuid given a video module.

        Implementation right now is a little hacky since we don't actually have a specific
        value for the relevant uuid, though we implicitly refer to all videos by their 1.0
        speed youtube uuids throughout the database.

        Example of the data associated with a video_module:

        <video youtube=\"0.75:-gKKUBQ2NWA,1.0:dJvsFg10JY,1.25:lm3IKbRE2VA,1.50:Pz0XiZ8wO9o\">
        """

        data = video_module.get("definition", {"data": ""}).get("data", "")
        if isinstance(data, dict):
            data = data.get("data", "")
        uuids = data.split(",")
        if len(uuids) == 1:  # Some videos are just left over demos without links
            return False
        # The colon is kind of a hack to make sure there will always be a second element since
        # some entries don't have anything for the second entry
        speed_map = {(entry + ":").split(":")[0]: (entry + ":").split(":")[1] for entry in uuids}
        uuid = [value for key, value in speed_map.items() if "1.0" in key][0]
        return uuid

    def thumbnail_from_pdf(self, pdf):
        """
        Converts a pdf to a jpg. Currently just takes the first page.
        """

        try:
            with Image(blob=pdf) as img:
                return base64.b64encode(img.make_blob('jpg'))
        except (DelegateError, MissingDelegateError, CorruptImageError):
            raise

    def thumbnail_from_html(self, html):
        """
        Wraps the given html in identifying tags

        On the front end these html elements will be drawn into canvas elements
        and then shrunk down to an appropriate size. Previous approach was to
        cast to pdf and then get a jpg. This is far more straight forward in my mind.
        """
        
        thumbnail = ("<svg xmlns='http://www.w3.org/2000/svg' width=200 height=200>"+
               "<foreignObject width='100%' height='100%'>" + html +
               "</foreignObject></svg>")
        return thumbnail

    def course_name_from_mongo_module(self, mongo_module):
        """
        Given a mongo_module, returns the name for the course element it belongs to
        """
        course_element = self.module_collection.find_one({
            "_id.course": mongo_module["_id"]["course"],
            "_id.category": "course"
        })
        return course_element["_id"]["name"]

    def basic_dict(self, mongo_module, type_):
        """
        Returns the part of the es schema that is the same for every object.
        """

        id_ = json.dumps(mongo_module["_id"])
        org = mongo_module["_id"]["org"]
        course = mongo_module["_id"]["course"]

        if not MONGO_COURSE_CACHE.get(course, False):
            MONGO_COURSE_CACHE[course] = self.course_name_from_mongo_module(mongo_module)
        offering = MONGO_COURSE_CACHE[course]

        course_id = "/".join([org, course, offering])
        hash_ = hashlib.sha1(id_).hexdigest()
        display_name = (
            mongo_module.get("metadata", {"display_name": ""}).get("display_name", "") +
            " (" + mongo_module["_id"]["course"] + ")"
        )
        searchable_text = self.get_searchable_text(mongo_module, type_)
        thumbnail = self.get_thumbnail(mongo_module, type_)
        type_hash = hashlib.sha1(course_id).hexdigest()
        return {
            "id": id_,
            "hash": hash_,
            "display_name": display_name,
            "course_id": course_id,
            "searchable_text": searchable_text,
            "thumbnail": thumbnail,
            "type_hash": type_hash
        }

    def get_searchable_text(self, mongo_module, type_):
        """
        Returns searchable text for a module. Defined for a module only
        """

        if type_.lower() == "pdf":
            name = re.sub(r'(.*?)(/asset/)(.*?)(\.pdf)(.*?)$', r'\3' + ".pdf", mongo_module["definition"]["data"])
            asset = self.find_asset_with_name(name)
            if not asset:
                searchable_text = ""
            else:
                searchable_text = self.pdf_to_text(asset)
        elif type_.lower() == "problem":
            searchable_text = self.searchable_text_from_problem_data(mongo_module)
        elif type_.lower() == "transcript":
            searchable_text = self.find_transcript_for_video_module(mongo_module)
        return searchable_text

    def get_thumbnail(self, mongo_module, type_):
        """
        General interface for getting an appropriate thumbnail for a given mongo module

        Currently the only types of modules supported ar pdfs, problems, and transcripts
        """
        if type_.lower() == "pdf":
            try:
                name = re.sub(r'(.*?)(/asset/)(.*?)(\.pdf)(.*?)$', r'\3' + ".pdf", mongo_module["definition"]["data"])
                asset = self.find_asset_with_name(name)
                if asset is None:
                    raise DelegateError
                thumbnail = self.thumbnail_from_pdf(asset.get("data", "").__str__())
            except (DelegateError, MissingDelegateError, CorruptImageError):
                thumbnail = ""
        elif type_.lower() == "problem":
            thumbnail = self.thumbnail_from_html(mongo_module["definition"]["data"])
        elif type_.lower() == "transcript":
            thumbnail = self.thumbnail_from_video_module(mongo_module)
        return thumbnail

    def bulk_index_item(self, index, data):
        """
        Returns a string representing the next indexing action for bulk index
        """

        return_string = ""
        return_string += json.dumps({"index": {"_index": index, "_type": data["type_hash"], "_id": data["hash"]}})
        return_string += "\n"
        return_string += json.dumps(data)
        return_string += "\n"
        return return_string

    def index_course(self, course):
        """
        Indexes all of the searchable content for a course
        """
        cursor = self.find_modules_for_course(course)
        log.debug("Course: %s" % course)
        log.debug(cursor.count())
        counter = 0
        for _ in range(cursor.count()):
            counter += 1
            item = cursor.next()
            category = item["_id"]["category"].lower().strip()
            if category != "html" and category != "discussion" and category != "customtag":
                log.debug(category)
            data = {}
            index = ""
            if category == "video":
                data = self.basic_dict(item, "transcript")
                log.debug(data)
                index = "transcript-index"
            elif category == "problem":
                data = self.basic_dict(item, "problem")
                index = "problem-index"
            # elif category == "html":
            #     pattern = re.compile(r".*?/asset/.*?\.pdf.*?")
            #     if pattern.match(item["definition"]["data"]):
            #         data = self.basic_dict(item, "pdf")
            #     else:
            #         data = {"test": ""}
            #     index = "pdf-index"
            else:
                continue
            if filter(None, data.values()) == data.values():
                self.es_instance.index_data(index, data, data["type_hash"], data["hash"]).content
