# functions to remove the class signature to allow http domain to document rest-apis
# from within the docstring

from sphinx.ext import autodoc
from sphinx.pycode import ModuleAnalyzer, PycodeError


def is_rest_api(processed_doc_string):
    # check whether the tag ":rest-api" is in the processed_doc_string
    is_rest = False
    for x in processed_doc_string:
        for y in x:
            if str(":rest-api") == str(y):
               is_rest = True
    return is_rest


class RESTDocumenterMixin(object):
    """
    Mixin for REST documentation to override the generate method in the RestMethodDocumenter
    and the RestClassDocumenter - which are inherited from autodoc.MethodDocumenter and
    autodoc.ClassDocumenter - which are, in turn, inherited from autodoc.Documenter
    """

    def generate(self, more_content=None, real_modname=None, check_module=False, all_members=False):
        # parse the name and the objects
        if not self.parse_name():
            return

        if not self.import_object():
            return

        if not is_rest_api(self.get_doc()):
            autodoc.Documenter.generate(self, more_content, real_modname, check_module, all_members)
        else:
            self.real_modname = real_modname or self.get_real_modname()
            try:
                self.analyzer = ModuleAnalyzer.for_module(self.real_modname)
                self.analyzer.find_attr_docs()
            except PycodeError as err:
                self.env.app.debug('[autodoc] module analyzer failed: %s', err)
                self.analyzer = None
                if hasattr(self.module, '__file__') and self.module.__file__:
                    self.directive.filename_set.add(self.module.__file__)
            else:
                self.directive.filename_set.add(self.analyzer.srcname)

            if check_module:
                if not self.check_module():
                    return

            sourcename = self.get_sourcename()

            # add all content (from docstrings, attribute docs etc.)
            self.add_content(more_content)

            self.indent += self.content_indent

            # document members, if possible
            self.document_members(all_members)


    def process_doc(self, docstrings):
        # remove the ":rest-api" docstring from the list of docstrings"
        if not is_rest_api(self.get_doc()):
            return autodoc.Documenter.process_doc(self, docstrings)
        else:
			new_docstrings = []
			for d in docstrings:
				for e in d:
					if not ":rest-api" == e:
						new_docstrings.append(e)
			return new_docstrings


class RestMethodDocumenter(RESTDocumenterMixin, autodoc.MethodDocumenter):
    pass


class RestClassDocumenter(RESTDocumenterMixin, autodoc.ClassDocumenter):
    pass


def setup():
    autodoc.add_documenter(RestMethodDocumenter)
    autodoc.add_documenter(RestClassDocumenter)
