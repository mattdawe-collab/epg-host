import gzip

from lxml import etree


def xmltv_time(moment):
    return moment.strftime("%Y%m%d%H%M%S +0000")


def make_source(path, programmes, names=None):
    """programmes: [(channel_id, start, stop, title)]; names: {channel_id: [display names]}."""
    names = dict(names or {})
    for channel_id, *_ in programmes:
        names.setdefault(channel_id, [channel_id])
    root = etree.Element("tv")
    for channel_id, display_names in names.items():
        channel = etree.SubElement(root, "channel", id=channel_id)
        for display in display_names:
            etree.SubElement(channel, "display-name").text = display
    for channel_id, start, stop, title in programmes:
        programme = etree.SubElement(root, "programme", start=xmltv_time(start), stop=xmltv_time(stop), channel=channel_id)
        etree.SubElement(programme, "title").text = title
    with gzip.open(path, "wb") as f:
        f.write(etree.tostring(root, xml_declaration=True, encoding="utf-8"))


def make_entity_source(path, secret_file, channel_id, start, stop):
    """A source whose names and titles pull in a local file through an external entity."""
    xml = (f'<?xml version="1.0"?><!DOCTYPE tv [<!ENTITY x SYSTEM "{secret_file.as_uri()}">]>'
           f'<tv><channel id="{channel_id}"><display-name>&x;</display-name></channel>'
           f'<programme start="{xmltv_time(start)}" stop="{xmltv_time(stop)}" channel="{channel_id}">'
           f'<title>&x;</title></programme></tv>')
    with gzip.open(path, "wb") as f:
        f.write(xml.encode("utf-8"))
