"""
This is the testing suite for the models within the search module
"""

from django.test import TestCase
from search.models import _snippet_generator, SearchResults
from test_mongo import dummy_document
from pyfuzz.generator import random_regex

import json

TEST_TEXT = "Lorem ipsum dolor sit amet, consectetur adipisicing elit, \
            sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. \
            Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris \
            nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in \
            reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. \
            Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia \
            deserunt mollit anim id est laborum"


def dummy_entry(score):
    """
    This creates a fully-fledged fake response entry for a given score
    """

    id_ = dummy_document("id", ["tag", "org", "course", "category", "name"], "regex", regex="[a-zA-Z0-9]", length=25)
    source = dummy_document("_source", ["thumbnail", "searchable_text"], "regex", regex="[a-zA-Z0-9]", length=50)
    string_id = json.dumps(id_["id"])
    source["_source"].update({"id": string_id, "course_id": random_regex(regex="[a-zA-Z0-9/]", length=50)})
    document = {"_score": score}
    source.update(document)
    return source


class FakeResponse():
    """
    Fake minimal response, just wrapping a given dictionary in a response-like object
    """

    def __init__(self, dictionary):
        self.content = json.dumps(dictionary)


class ModelTest(TestCase):
    """
    Tests SearchResults and SearchResult models as well as associated helper functions
    """

    def test_snippet_generation(self):
        snippets = _snippet_generator(TEST_TEXT, "quis nostrud", bold=False)
        self.assertTrue(snippets.startswith("Ut enim ad minim"))
        self.assertTrue(snippets.endswith("anim id est laborum"))

    def test_highlighting(self):
        highlights = _snippet_generator(TEST_TEXT, "quis nostrud")
        self.assertTrue(highlights.startswith("Ut enim ad minim"))
        self.assertTrue(highlights.strip().endswith("anim id est laborum"))
        self.assertTrue("<b class=highlight>quis</b>" in highlights)
        self.assertTrue("<b class=highlight>nostrud</b>" in highlights)

    def test_search_result(self):
        scores = [1.0, 5.2, 2.0, 123.2]
        hits = [dummy_entry(score) for score in scores]
        full_return = FakeResponse({"hits": {"hits": hits}})
        results = SearchResults(full_return, s="fake query", sort="relevance")
        results.filter_and_sort()
        scores = [entry.score for entry in results.entries]
        self.assertEqual([123.2, 5.2, 2.0, 1.0], scores)
