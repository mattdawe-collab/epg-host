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
