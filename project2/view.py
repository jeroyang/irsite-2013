import webapp2
from models import *
import re
import os
import jinja2
import cPickle as pickle
import time
import itertools

jinja_environment = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), '../templates')))

class MainPage(webapp2.RequestHandler):
    def get(self):
        start_time = time.time()
        self.response.headers['Content-Type'] = 'text/html'
        index_term = self.request.get('i')
        query_term = self.request.get('q')
        start_result = self.request.get('start')

        if index_term and index_term != '': 
            f = Fetcher(limit=10)
            f.fetch_to_db_quick(index_term, True)
        elif query_term and query_term != '': # There is a query
            if start_result == '':
                start_result = 0
            else:
                start_result = int(start_result)
            token = normalize(word_tokenize(query_term)[0]) # that is temp solver for only one token
            train = Train.get_by_key_name(token)
            if train is None:
                articles = []
                search_overview = 'No result was found about %s' % query_term
                nav_bar = None
            else: 
                cars = pickle.loads(train.cars)
                if len(cars) <= 10:
                    articles = [(car[0], Article.get_by_key_name(car[0]).title) for car in cars]
                    nav_bar = None
                else:
                    car_slice = itertools.islice(cars, start_result, start_result+10)
                    articles = [(car[0], Article.get_by_key_name(car[0]).title) for car in car_slice]
                    nav_bar = start_result
                search_overview = 'About %i results in %f second.' % (len(cars), time.time()-start_time)
            template_values = { 'search_overview': search_overview,
                            'query_term': query_term,
                            'results': articles,
                            'nav_bar': nav_bar}
        else: # There is no query
            template_values = {'nav_bar': None,
                               'results': None,
                               'search_overview': None,
                               'nav_bar': None}
        
        template = jinja_environment.get_template('project2.html')
        self.response.out.write(template.render(template_values))
        
    def post(self):
        pass

        
app = webapp2.WSGIApplication([('/', MainPage), ('/project2', MainPage)], debug=True)