"""Adds the package cache's server and Central mirror to a Maven settings file.

Usage: maven-settings.py <settings.xml>

The file is created when it does not exist. An existing one, such as the one actions/setup-java
writes, keeps everything it has; the cache's server and mirror entries (id `package-cache`) are
added or replaced. The token stays in the environment (${env.PACKAGE_CACHE_TOKEN}), never on disk.
"""

import sys
import xml.etree.ElementTree as ET

ID = 'package-cache'


def main(path):
    try:
        tree = ET.parse(path)
    except FileNotFoundError:
        tree = ET.ElementTree(ET.Element('settings'))
    root = tree.getroot()
    if root.tag.split('}')[-1] != 'settings':
        sys.exit(f'package-cache: {path} is not a Maven settings file (root <{root.tag}>)')
    ns = root.tag[: root.tag.index('}') + 1] if root.tag.startswith('{') else ''
    if ns:
        ET.register_namespace('', ns[1:-1])
    ET.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')

    def child(parent, name):
        found = parent.find(ns + name)
        if found is None:
            found = ET.SubElement(parent, ns + name)
        return found

    def replace_entry(section, entry, fields):
        parent = child(root, section)
        for old in parent.findall(ns + entry):
            if (old.findtext(ns + 'id') or '').strip() == ID:
                parent.remove(old)
        new = ET.SubElement(parent, ns + entry)
        for name, value in fields:
            ET.SubElement(new, ns + name).text = value
        return parent

    mirrors = child(root, 'mirrors')
    for mirror in mirrors.findall(ns + 'mirror'):
        mirror_id = (mirror.findtext(ns + 'id') or '').strip()
        mirror_of = {part.strip() for part in (mirror.findtext(ns + 'mirrorOf') or '').split(',')}
        if mirror_id != ID and mirror_of & {'central', '*', 'external:*'}:
            sys.exit(f'package-cache: {path} already mirrors central through "{mirror_id}"')

    replace_entry('servers', 'server', [
        ('id', ID),
        ('username', 'ci'),
        ('password', '${env.PACKAGE_CACHE_TOKEN}'),
    ])
    replace_entry('mirrors', 'mirror', [
        ('id', ID),
        ('mirrorOf', 'central'),
        ('url', '${env.PACKAGE_CACHE_URL}/maven'),
    ])
    ET.indent(tree)
    tree.write(path, encoding='utf-8', xml_declaration=True)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
