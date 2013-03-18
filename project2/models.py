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
    pmid = db.IntegerProperty() # We should also use the pmid as the key_name, so, we will have two attributes contains the pmid
    title = db.StringProperty()
    authors = db.StringProperty()
    journal = db.StringProperty()
    pub_date = db.DateProperty()
    fulltext = db.TextProperty()
    fetch_time = db.DateTimeProperty(auto_now=True)

class Fetcher(object):
    """A Fecther which can download pubmed articles"""
    def __init__(self, limit=0):
        """The teacher said that we only fetch the first 1000 articles about CD63"""
        self.limit = limit

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
        return [int(pmid) for pmid in output]

    def _get_articles(self, pmid_list, limit):
        """Return a file object of specific pmids"""
        url = 'http://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
        if limit > 0:
            pmid_list = pmid_list[0:limit]

        post_data = [('db', 'pubmed'),
                     ('id', ','.join([str(i) for i in pmid_list])),
                     ('retmode', 'xml')]
        return urlopen(url, urlencode(post_data))

    def fetch_to_db_quick(self, query_term, make_index=True):
        if make_index: 
            iindex = InvertedIndex()
        with open('cd63.xml') as cd63:
            tree = etree.parse(cd63)

        def _safe_find(tag, xmltree):
            if xmltree.find('.//%s' % tag) == None:
                return etree.Element(tag)
            else:
                return xmltree.find('.//%s' % tag)
    
        for article in tree.findall('.//MedlineCitation'):
            d = _safe_find('Pubdate', article)
            try:
                pub_date = datetime.datetime.strptime(" ".join((d.findtext("./Year"), d.findtext("./Month"), d.findtext("./Day"))), "%Y %b %d").date()
            except:
                pub_date = None
            this_article = Article(id=int(article.findtext(".//PMID")), 
                pmid=int(article.findtext(".//PMID")),
                title=article.findtext(".//ArticleTitle"),
                authors=", ".join("%s %s" % (author.findtext("LastName"), author.findtext("ForeName")) for author in article.findall(".//Author")),
                journal=article.findtext(".//Journal/Title"),
                pub_date=pub_date,
                fulltext="\n".join([a.text or '' for a in article.findall('.//Abstract/*')]))
            this_article.put()
            if make_index:
                iindex.put(this_article)
        if make_index:
            iindex.save()
        del tree

    def fetch_to_db(self, query_term, make_index=False):

        if make_index: 
            iindex = InvertedIndex()
        tree = etree.parse(self._get_articles(self._get_pmids(query_term), self.limit))

        def _safe_find(tag, xmltree):
            if xmltree.find('.//%s' % tag) == None:
                return etree.Element(tag)
            else:
                return xmltree.find('.//%s' % tag)
    
        for article in tree.findall('.//MedlineCitation'):
            d = _safe_find('Pubdate', article)
            try:
                pub_date = datetime.datetime.strptime(" ".join((d.findtext("./Year"), d.findtext("./Month"), d.findtext("./Day"))), "%Y %b %d").date()
            except:
                pub_date = None
            this_article = Article(id=int(article.findtext(".//PMID")), 
                pmid=int(article.findtext(".//PMID")),
                title=article.findtext(".//ArticleTitle"),
                authors=", ".join("%s %s" % (author.findtext("LastName"), author.findtext("ForeName")) for author in article.findall(".//Author")),
                journal=article.findtext(".//Journal/Title"),
                pub_date=pub_date,
                fulltext="\n".join([a.text or '' for a in article.findall('.//Abstract/*')]))
            this_article.put()
            if make_index:
                iindex.put(this_article)
        if make_index:
            iindex.save()
        del tree


class Train(db.Model):
    """The db object for PositionalPostingList which contains the postings about one specific token
    document_frequency
    posting_list = pickle.load(positional_index) 
    posting_list = deque([  (article.pmid, term_frequency, posting_deque([token_position, token_position, ...])),
                             (article.pmid, term_frequency, posting_deque([token_position, token_position, ...])),
                             ...  
                           ])
    """
    token = db.StringProperty()# We should use the token as the key_name
    document_frequency = db.IntegerProperty()
    cars = db.BlobProperty()


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
        for token, cars in self.auxiliary_index.items():
            train = Train.all().filter('token=', token)

            if sum(1 for _ in train)==0:
                Train(key_name=token, token=token, document_frequency=1, cars=pickle.dumps(cars)).put()
            else: 
                train[0].document_frequency += 1
                new_cars = pickle.loads(train[0].cars).extend(cars)
                train[0].cars = pickle.dumps(new_cars)
                train.put()
                

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
            self.tf_dict[train.token] = sum([tf for (id_, tf, sits) in cars])

    def get_dict(self):
        return self.tf_dict

    def get_list(self):
        return [[key, value] for key, value in self.tf_dict.iteritems()]

    def get_sorted_list(self):
        return sorted(self.get_list(), cmp=lambda x,y: x[1]-y[1], reverse=True)

