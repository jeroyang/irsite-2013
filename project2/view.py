import webapp2
from models import *
import re
import os
import jinja2
import cPickle as pickle

jinja_environment = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), '../templates')))

class MainPage(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/html'
        index_term = self.request.get('i')
        query_term = self.request.get('q')
        pmids = []
        if index_term and index_term != '': 
            f = Fetcher(limit=10)
            f.fetch_to_db_quick(index_term, True)
        if query_term and query_term != '':
            token = normalize(word_tokenize(query_term)[0]) # that is temp solver for only one token
            q = Train.all()
            train = q
            if sum(1 for _ in train)!=0:
                cars = pickle.loads(train[0].cars)
                pmids = [car[0] for car in cars]

        tf_list = ",".join(["[%i,%i,\"%s\"]" % (ix, item[1], item[0]) for ix, item in enumerate(TermFrequency().get_sorted_list())])
        template_values = {'tf_list': tf_list,
                            'results': pmids}
        template = jinja_environment.get_template('project2.html')
        self.response.out.write(template.render(template_values))
        
    def post(self):
        pass

        
app = webapp2.WSGIApplication([('/', MainPage), ('/project2', MainPage)], debug=True)