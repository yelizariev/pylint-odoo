import io
import re
import ast
import os
import types
import astroid
import sys
from pylint.checkers import BaseChecker, utils
from pylint.interfaces import IAstroidChecker
from .. import misc, settings

def _is_string_instance(obj):
	try:
		return isinstance(obj, basestring)
	except NameError:
		return isinstance(obj, str)


ITP_ODOO_MSGS = {
    # C->convention R->refactor W->warning E->error F->fatal
    'E%d99' % settings.BASE_OMODULE_ID: (
        'Placeholder "%s" is not updated',
        'manifest-template-field',
        settings.DESC_DFLT
    ),
    'E%d98' % settings.BASE_OMODULE_ID: (
        'File: doc/index.rst is absent in module. Get a template here: https://odoo-development.readthedocs.io/en/latest/dev/docs/usage-instructions.html',
        'absent-doc',
        settings.DESC_DFLT
    ),
    'E%d97' % settings.BASE_OMODULE_ID: (
        'File: doc/changelog.rst is absent in module. Get a template here: https://odoo-development.readthedocs.io/en/latest/dev/docs/changelog.rst.html',
        'absent-changelog',
        settings.DESC_DFLT
    ),
    'E%d96' % settings.BASE_OMODULE_ID: (
        'File: %s - Template placeholder "%s" is not updated',
        'rst-template-field',
        settings.DESC_DFLT
    ),
    'E%d95' % settings.BASE_OMODULE_ID: (
        'File: static/description/icon.png is absent in module. Get possible icons here: https://odoo-development.readthedocs.io/en/latest/dev/docs/icon.png.html',
        'absent-icon',
        settings.DESC_DFLT
    ),
    'E%d94' % settings.BASE_OMODULE_ID: (
        'Duplicated xml id: "%s" in file: "%s" and file: "%s". Did you forget to update name after copy-paste?',
        'xml-id-duplicated',
        settings.DESC_DFLT
    ),
    'W%d93' % settings.BASE_OMODULE_ID: (
        'JS files are not covered (phantom_js is not used). Please add js tests: https://odoo-development.readthedocs.io/en/latest/qa/js/index.html',
        'js-empty-coverage',
        settings.DESC_DFLT
    ),
    'E%d92' % settings.BASE_OMODULE_ID: (
        'File: static/description/index.html is absent in module. Contact Technical Writers for assistance',
        'absent-index-html',
        settings.DESC_DFLT
    ),
    'E%d91' % settings.BASE_OMODULE_ID: (
        'Module\'s image is absent or it\'s not in images/ folder. Check attribute "images" in module\'s __manifest__.py',
        'manifest-image',
        settings.DESC_DFLT
    ),
    'E%d90' % settings.BASE_OMODULE_ID: (
        'Wrong version value in module\'s __manifest__.py',
        'manifest-version',
        settings.DESC_DFLT
    ),
}
TEMPLATE_RE = '(?<!\$){[_ a-zA-Z0-9,./\'"]*}'
TEMPLATE_FILES = ('README.rst', 'doc/index.rst', 'doc/changelog.rst')


class ITPModuleChecker(misc.WrapperModuleChecker):
    __implements__ = IAstroidChecker
    name = settings.CFG_SECTION
    # name = 'itplynt'
    msgs = ITP_ODOO_MSGS

    @utils.check_messages(*(ITP_ODOO_MSGS.keys()))
    def visit_module(self, node):
        self.wrapper_visit_module(node)

    @utils.check_messages('manifest-template-field')
    def visit_dict(self, node):
        if not os.path.basename(self.linter.current_file) in settings.MANIFEST_FILES \
                or not isinstance(node.parent, astroid.Discard):
            return
        manifest_dict = ast.literal_eval(node.as_string())

        # Check all template fields filled
        for k, v in manifest_dict.items():
            if _is_string_instance(v):
                match = re.match(TEMPLATE_RE, v)
                if match:
                    self.add_message('manifest-template-field', node=node, args=v)

    def open(self):
        """Define variables to use cache"""
        self.inh_dup = {}
        super(ITPModuleChecker, self).open()

    def close(self):
        """Final process get all cached values and add messages"""
        for (odoo_node, class_dup_name), nodes in self.inh_dup.items():
            if len(nodes) == 1:
                continue
            path_nodes = []
            for node in nodes[1:]:
                relpath = os.path.relpath(node.file,
                                          os.path.dirname(odoo_node.file))
                path_nodes.append("%s:%d" % (relpath, node.lineno))
            self.add_message('consider-merging-classes-inherited',
                             node=nodes[0],
                             args=(class_dup_name, ', '.join(path_nodes)))

    @utils.check_messages('absent-doc')
    def _check_absent_doc(self):
        return os.path.isfile(os.path.join(self.module_path, 'doc/index.rst'))

    @utils.check_messages('absent-index-html')
    def _check_absent_index_html(self):
        return os.path.isfile(os.path.join(self.module_path, 'static/description/index.html'))

    @utils.check_messages('manifest-image')
    def _check_manifest_image(self):
        manifest_dict = self.manifest_dict
        if "images" in manifest_dict.keys():
            images = manifest_dict.get('images', [])
            if images != []:
                for image in images:
                    if image.startswith("images/"):
                        return os.path.isfile(os.path.join(self.module_path, image))
                    else:
                        return False
            else:
                return False

    @utils.check_messages('manifest-version')
    def _check_manifest_version(self):
        manifest_dict = self.manifest_dict
        if "version" in manifest_dict.keys():
            version = manifest_dict.get('version', '')
            installable = manifest_dict.get('installable', True)
            if version != '':
                manifest_odoo_version = '.'.join(version.split('.')[:2])
                valid_odoo_version = self.linter._all_options[
                'valid_odoo_versions'].config.valid_odoo_versions[0]
                if sys.version_info[0] == 2:
                    valid_odoo_version = valid_odoo_version.encode('utf-8')
                if manifest_odoo_version != valid_odoo_version and installable:
                    print("Odoo version from ___manifest__.py is %s" % (manifest_odoo_version))
                    print("Expected odoo version is %s" % (valid_odoo_version))
                    return False
                else:
                    return True
            else:
                return False

    @utils.check_messages('absent-changelog')
    def _check_absent_changelog(self):
        return os.path.isfile(os.path.join(self.module_path, 'doc/changelog.rst'))

    @utils.check_messages('absent-icon')
    def _check_absent_icon(self):
        return os.path.isfile(os.path.join(self.module_path, 'static/description/icon.png'))

    @utils.check_messages('rst-template-field')
    def _check_rst_template_field(self):
        rst_files = self.filter_files_ext('rst')
        self.msg_args = []
        for rst_file in rst_files:
            if rst_file in TEMPLATE_FILES:
                f = io.open(os.path.join(self.module_path, rst_file))
                content = f.read()
                f.close()
                match = re.findall(TEMPLATE_RE, content)
                if len(match):
                    for rec in match:
                        self.msg_args.append(("%s" % rst_file, rec))
        if self.msg_args:
            return False
        return True

    @utils.check_messages('xml-id-unique')
    def _check_xml_id_duplicated(self):
        xml_files = self.filter_files_ext('xml')
        self.msg_args = []
        xml_ids = []
        for xml_file in xml_files:
            result = self.parse_xml(os.path.join(self.module_path, xml_file))
            match = result.xpath('data/record') if not _is_string_instance(result) else []
            if len(match):
                for rec in match:
                    xml_ids.append((xml_file, rec.attrib['id']))
        ln = len(xml_ids)
        for i in range(ln):
            for j in range(i+1, ln):
                if xml_ids[i][1] == xml_ids[j][1]:
                    self.msg_args.append((xml_ids[j][1], xml_ids[i][0], xml_ids[j][0]))
        if self.msg_args:
            return False
        return True

    @utils.check_messages('js-empty-coverage')
    def _check_js_empty_coverage(self):
        js_files =  [
            fname for fname in self.filter_files_ext('js')
            if not fname.startswith('static/lib')
        ]
        if not js_files:
            return True


        xml_ids = []
        for pyfile in self.filter_files_ext('py'):
            if not pyfile.startswith('tests/'):
                continue
            # TODO parse python code instead of using regexp
            f = io.open(os.path.join(self.module_path, pyfile))
            content = f.read()
            f.close()
            for rexp in ['self\.phantom_js', 'self\.browser_js', 'self\.url_open']: 
                match = re.findall(rexp, content)
                if len(match):
                    return True

        return False

