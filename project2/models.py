import datetime
from google.appengine.ext import db
from collections import Counter, deque, defaultdict
from itertools import chain
import sys
sys.path.append('/usr/local/Cellar/python/2.7.2/Frameworks/Python.framework/Versions/2.7/lib/python2.7/site-packages')
from lxml import etree
from urllib2 import urlopen
from urllib import quote_plus, urlencode
import re
import cPickle as pickle
import string


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

class Article(db.Model):
    # key_name = str(pmid)
    title = db.StringProperty()
    authors = db.StringProperty()
    journal = db.StringProperty()
    pub_date = db.DateProperty()
    fulltext = db.TextProperty()
    fetch_time = db.DateTimeProperty(auto_now=True)
    is_indexed = db.BooleanProperty()

class Fetcher(object):

    def _get_pmids(self, query_term, ret_max=1000):
        ret_start = 0
        output = []

        while True:
            url = 'http://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=%s&retstart=%s&retmax=%s'\
            % (quote_plus(query_term), ret_start, ret_max)
            tree = etree.parse(urlopen(url))
            count = int(tree.xpath('/eSearchResult/Count/text()')[0])
            ret_max = int(tree.xpath('/eSearchResult/RetMax/text()')[0])
            output.extend(tree.xpath('/eSearchResult/IdList/Id/text()'))

            if ret_start + ret_max < count:
                ret_start += ret_max
            else:
                break
        return output

    def _get_articles(self, pmid_list):
        """Return a file object of specific pmids"""
        url = 'http://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
        post_data = [('db', 'pubmed'),
                     ('id', ','.join(pmid_list)),
                     ('retmode', 'xml')]
        return urlopen(url, urlencode(post_data))

    def fetch_to_db(self, query_term, limit=None):

        iindex = InvertedIndex()
        if limit is not None:
            tree = etree.parse(self._get_articles(self._get_pmids(query_term)[0:limit]))

        for article in tree.findall('.//MedlineCitation'):
            d = " ".join(article.xpath('.//PubDate/*/text()'))
            try:
                if re.match(r'\d{4} \w{3} \d{1,2}$', d):
                    pub_date = datetime.datetime.strptime(d, "%Y %b %d").date()
                elif re.match(r'\d{4} \w{3}$', d):
                    pub_date = datetime.datetime.strptime(d, "%Y %b").date()
                else:
                    pub_date = datetime.datetime.strptime(d[0:4], "%Y").date()
            except:
                pub_date = None

            this_article = Article(
                key_name=article.xpath("./PMID[1]/text()")[0],
                title=unicode(article.xpath(".//ArticleTitle/text()")[0]),
                authors=u", ".join([" ".join(author.xpath('./ForeName/text()|./LastName/text()')) for author in article.xpath('.//Author')]),
                journal=unicode(article.xpath(".//Journal/Title/text()")[0]),
                pub_date=pub_date,
                fulltext=u"\n".join(article.xpath('.//Abstract/*/text()'))
            )
            this_article.put()
            iindex.put(this_article)

        iindex.save()
        del tree


class Train(db.Model):
    """A train is a complete posting list for a specific token"""
    # key_name = token
    document_frequency = db.IntegerProperty()
    cars = db.BlobProperty()

class InvertedIndex(object):
    def __init__(self):
        self.auxiliary_index = defaultdict(deque)

    def put(self, article):
        """article is an instance of Article, we are talking a specific car number (but in many trains) here"""
        car = defaultdict(deque)
        tokens = chain.from_iterable(word_tokenize(sentence) for sentence \
            in sentence_tokenize("\n".join([article.key().name(), article.title, article.authors, article.journal, article.fulltext])))
        for sit, token in enumerate(tokens):
            if normalize(token) != None:
                car[normalize(token)].append(sit) # Finally, we will have a dictionary of toke:deque(positions) pair

        for token, sits in car.items():
            self.auxiliary_index[token].append((article.key().name(), len(sits), sits))

    def save(self):
        for token, cars in self.auxiliary_index.items():
            Train(key_name=token, document_frequency=len(cars), cars=pickle.dumps(cars)).put()

class SpellingCorrector(object):
    """A class of spelling corrector."""
    def __init__(self):
        self.NWORDS = db.Query(Train).all(keys_only=True)
        
    def _edits1(self, word):
        splits     = [(word[:i], word[i:]) for i in range(len(word) + 1)]
        deletes    = [a + b[1:] for a, b in splits if b]
        transposes = [a + b[1] + b[0] + b[2:] for a, b in splits if len(b)>1 ]
        replaces   = [a + c + b[1:] for a,b in splits for c in string.printable if b]
        inserts    = [a + c+ b for a, b in splits for c in string.printable]
        return set(deletes + transposes + replaces + inserts)
        
    def _known_edits2(self, word):
        return set(e2 for e1 in self._edits1(word) for e2 in self._edits1(e1) if e2 in self.NWORDS)
    
    def _known(self, words):
        return set(w for w in words if w in self.NWORDS)
    
    def correct(self, word):
        candidates = self._known([word]) or self._known(self._edits1(word)) or self._known_edits2(word) or [word]
        return max(candidates, key=self.NWORDS.get)


class TermFrequency(object):
    def __init__(self):
        self.tf_dict = dict()
        q = Train.all()
        for train in q:
            cars = pickle.loads(train.cars)
            self.tf_dict[train.key().name()] = sum([tf for (id_, tf, sits) in cars])

    def get_dict(self):
        return self.tf_dict

    def get_list(self):
        return [[key, value] for key, value in self.tf_dict.iteritems()]

    def get_sorted_list(self):
        return sorted(self.get_list(), cmp=lambda x,y: x[1]-y[1], reverse=True)

