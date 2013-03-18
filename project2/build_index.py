import webapp2
from models import *
import re
import os
import jinja2
from urllib2 import urlopen
from urllib import quote_plus, urlencode
from lxml import etree

jinja_environment = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), '../templates')))

class MainPage(webapp2.RequestHandler):
    def get(self):
        def _safe_find(tag, xmltree):
        if xmltree.find('.//%s' % tag) == None:
            return etree.Element(tag)
        else:
            return xmltree.find('.//%s' % tag)

        self.response.headers['Content-Type'] = 'text/html'
        query_term = self.request.get('q')
        if query_term:
            Fetcher.fetch_to_db('CD63')
        #template = jinja_environment.get_template('project2.html')
        #self.response.out.write(template.render(template_values))
        
    def post(self):
        self.response.headers['Content-Type'] = 'text/html'
        xmls = [self.request.get(field_name) for field_name in ['xml_file1', 'xml_file2']]
        try:
            xml_document = [XmlDocument(xml) for xml in xmls]
            my_comparator = Comparator(*xml_document)

            template_values = {'has_result' : True, 
        				   'common_word_cloud' : my_comparator.common_word_cloud(), 
                           'document_list' : my_comparator.document_list_html('word_'),
                           'statistics_list': my_comparator.statistics_list_html(),
        				   'xml' : xml_document}
        except:
            if 0 in [len(xml) for xml in xmls]:
                template_values = {'has_result' : False,
                                'alert' : 'Empty XML, please upload TWO valid Pubmed XML'}
            else:
                template_values = {'has_result' : False,
                                'alert' : 'Invalid XML format, only Pubmed XML is accepted. '}
        template = jinja_environment.get_template('project1.html')
        self.response.out.write(template.render(template_values))

        
app = webapp2.WSGIApplication([('/', MainPage), ('/project2', MainPage)], debug=True)