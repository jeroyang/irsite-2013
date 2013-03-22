from lxml import etree
from collections import defaultdict, deque
from itertools import chain
import re
import string
import cPickle as pickle

def sentence_tokenize(s):
    """Cut the document into sentences without modifying anything"""
    s = re.sub(r'([!,\.:;?][\s\n])', r' \1', s)
    return s.split()

def word_tokenize(s):
    """Cut the sentence in into tokens without modifying anything"""
    s = re.sub(r'(?P<left>(^|[\s\n])")(?P<middle>[^"]?)(?P<right>"([ ,.!?\s]|$))', '\g<left> \g<middle> \g<right>', s)
    s = re.sub(r'(?P<left>(^|[\s\n])\')(?P<middle>[^\']?)(?P<right>\'([ ,.!?\s]|$))', '\g<left> \g<middle> \g<right>', s)
    s = re.sub(r'(?P<left>(^|[\s\n])\()(?P<middle>[^\(]?)(?P<right>\)([ ,.!?\s]|$))', '\g<left> \g<middle> \g<right>', s)
    s = re.sub(r'(?P<left>(^|[\s\n])\[)(?P<middle>[^\[]?)(?P<right>\]([ ,.!?\s]|$))', '\g<left> \g<middle> \g<right>', s)
    s = re.sub(r'(?P<left>(^|[\s\n])\{)(?P<middle>[^\{]?)(?P<right>\}([ ,.!?\s]|$))', '\g<left> \g<middle> \g<right>', s)
    return s.split()

def normalize(token):

    token = re.sub(r'[%s]' % re.escape(string.punctuation), '', token).lower()
    if token != '':
        return token

class InvertedIndex(object):
    def __init__(self):
        self.auxiliary_index = defaultdict(deque)

    def put(self, article):
        """article is an instance of Article, we are talking a specific car number (but in many trains) here"""
        car = defaultdict(deque)
        tokens = chain.from_iterable(word_tokenize(sentence) for sentence \
            in sentence_tokenize("\n".join([str(article.pmid), article.title, article.authors, article.journal, article.fulltext])))
        for sit, token in enumerate(tokens):
            if normalize(token) != None:
                car[normalize(token)].append(sit) # Finally, we will have a dictionary of toke:deque(positions) pair

        for token, sits in car.items():
            self.auxiliary_index[token].append((article.pmid, len(sits), sits))
    def save(self):
        for key, train in self.auxiliary_index.items():
            with open('index/%s.txt' % key, 'w') as out:
                out.write(str(train))

class Article(object):
    def __init__(self, id, pmid, title, authors, journal, pub_date, fulltext):
        self.id = id
        self.pmid = pmid
        self.title = title
        self.authors = authors
        self.journal = journal
        self.pub_date = pub_date
        self.fulltext = fulltext

    def put(self):
        pass

def fetch_to_db_quick(query_term='CD63', make_index=True):
        if make_index: 
            iindex = InvertedIndex()
        with open('../cd63.xml') as cd63:
            tree = etree.parse(cd63)
        
        for article in tree.findall('.//MedlineCitation'):
            " ".join([s.strip() for s in tree.xpath('.//PubDate//text()') if s.strip() != ''])
            this_article = Article(id=int(article.findtext(".//PMID")), 
                pmid=int(article.findtext(".//PMID")),
                title=article.findtext(".//ArticleTitle"),
                authors=", ".join("%s %s" % (author.findtext("LastName"), author.findtext("ForeName")) for author in article.findall(".//Author")),
                journal=article.findtext(".//Journal/Title"),
                pub_date='',
                fulltext="\n".join([a.text or '' for a in article.findall('.//Abstract/*')]))
            this_article.put()
            if make_index:
                iindex.put(this_article)
        if make_index:
            iindex.save()
        del tree

fetch_to_db_quick()
