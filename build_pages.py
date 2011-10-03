import sys, os, sqlite3, shutil, datetime
from docutils import io
from docutils.utils import SystemMessage
from docutils.core import publish_cmdline, default_description, publish_programmatically

"""run python build_page.py base_path"""

class Bag:
    pass

settings=Bag()


st={'HTTP_BASE':'hp/'}


st['GENLINK_PREFIX']='<div class="genlink_prefix h2">Related Links</div>'
st['GENTAG_PREFIX']='<div class="gentag_prefix h2">Tags</div>'
st['LINK_TO_TAG_PAGES']=0

settings.__dict__.update(st)

settings.HEADER=open('header.html','r').read()
settings.FOOTER=open('footer.html','r').read()%(str(datetime.datetime.now()))

rstdata={}

def publish_file(source=None, source_path=None,
                 destination=None, destination_path=None,
                 reader=None, reader_name='standalone',
                 parser=None, parser_name='restructuredtext',
                 writer=None, writer_name='pseudoxml',
                 settings=None, settings_spec=None, settings_overrides=None,
                 config_section=None, enable_exit_status=None):
    """
    Set up & run a `Publisher` for programmatic use with file-like I/O.
    Return the encoded string output also.

    Parameters: see `publish_programmatically`.
    """
    output, pub = publish_programmatically(
        source_class=io.FileInput, source=source, source_path=source_path,
        destination_class=io.FileOutput,
        destination=destination, destination_path=destination_path,
        reader=reader, reader_name=reader_name,
        parser=parser, parser_name=parser_name,
        writer=writer, writer_name=writer_name,
        settings=settings, settings_spec=settings_spec,
        settings_overrides=settings_overrides,
        config_section=config_section,
        enable_exit_status=enable_exit_status)
    return pub

def isrst(fp):
    return fp.endswith('.rst')

def full_relative_paths_to_rsts(base):
    res=[]
    for f in os.listdir(base):
        fpath=os.path.join(base, f)
        if os.path.isfile(fpath):
            if isrst(fpath):
                res.append(fpath)
        elif os.path.isdir(fpath):
            subres=full_relative_paths_to_rsts(fpath)
            res.extend(subres)
    return res

def make_htmls(rsts):
    dat={}
    #dat stores extra data - might as well just keep this.
    for rst in rsts:
        try:
            destpath=rst.replace('.rst','.html')

            settings_overrides={'stylesheet_path':'html4css1.css,hpcss.css',
                'theme':'big-black',
                }
            pub=publish_file(source_path=rst, writer_name='html', destination_path=destpath, settings_overrides=settings_overrides)
            dat[rst]={'title':pub.document.get('title')}
            #~ import ipdb;ipdb.set_trace();print 'in ipdb!'
        except SystemMessage:
            print 'problem with:',rst
            import ipdb;ipdb.set_trace();print 'in ipdb!'
        except:
            print 'other problem!'
            import traceback
            traceback.print_exc()
            import ipdb;ipdb.set_trace();print 'in ipdb!'
    return dat

def get_tags(rst):
    tags=[]
    for l in open(rst,'r').readlines():
        if l.startswith('tags:'):
            l=l.split('tags:')[-1]
            tags.extend([tag.strip().lower() for tag in l.split(',') if tag])
    return tags

def add_tags_to_db(rst, tags):
    conn = sqlite3.connect('tmpdb')
    c=conn.cursor()

    for tag in tags:
        c.execute('''insert into rst2tag (rst, tag) values ("%s","%s") '''%(rst, tag))
    conn.commit()
    c.close()

def recreate_db():
    if os.path.exists('tmpdb'):
        os.remove('tmpdb')
    conn = sqlite3.connect('tmpdb')
    c=conn.cursor()
    c.execute('''create table rst2tag
        (rst text,  tag text)''')
    conn.commit()
    c.close()

def tags_from_db(rst):
    conn = sqlite3.connect('tmpdb')
    c=conn.cursor()
    res=c.execute('select tag from rst2tag where rst="%s"'%rst).fetchall()
    return [r[0] for r in res]
    #~ return res

def tag2rsts(tag, exclude=None):
    conn = sqlite3.connect('tmpdb')
    c=conn.cursor()
    res=c.execute('select rst from rst2tag where tag="%s"'%tag).fetchall()
    res=[r[0] for r in res if r[0] not in exclude]
    return res

def get_related_rsts(rst, tags):
    res={}
    for tag in tags:
        rsts=tag2rsts(tag, exclude=rst)
        for subrst in rsts:
            res[subrst]=res.get(subrst,0)+1
    return sorted(list(res), key=lambda x:-1*x[1])

def make_link_section(rsts):
    res=[]
    for rst in rsts:
        fn=os.path.split(rst)[1]
        try:
            title=rstdata[rst]['title']
            if title is None:
                title='no title %s'%rst
        except:
            title='TITLEMISSING %s'%rst
            import ipdb;ipdb.set_trace();print 'in ipdb!'
        htmlpath=settings.HTTP_BASE+'/'+rst2htmlpath(rst)
        htmlpath='%s/%s'%(settings.HTTP_BASE,rst2htmlpath(rst))
        pt='<div class="genlink"><a href="%s">%s</a></div>'%(htmlpath, title)
        res.append(pt)
    res='<div class="genlink_section">%s%s</div>'%(settings.GENLINK_PREFIX, ''.join(res))
    return res

def make_tag_section(tags, link=True):
    res=[]
    for tag in tags:
        taglink='%s/tags/%s'%(settings.HTTP_BASE, tag)
        if link:
            pt='<div class="gentag"><a href="%s">%s</a></div>'%(taglink, tag)
        else:
            pt='<div class="gentag">%s</div>'%(tag)
        res.append(pt)
    res='<div class="gentag_section">%s%s</div>'%(settings.GENTAG_PREFIX, ''.join(res))
    return res

def put_stuff_into_html(html, related_rsts, tags):
    assert html.endswith('.html')
    lines=open(html,'r').readlines()
    linksection=make_link_section(related_rsts)
    tagsection=make_tag_section(tags, link=settings.LINK_TO_TAG_PAGES)
    out=open(html,'w')
    for l in lines:
        #~ import ipdb;ipdb.set_trace();print 'in ipdb!'
        if '</body>' in l:
            #~ import ipdb;ipdb.set_trace();print 'in ipdb!'
            l=l.replace('</body>', settings.FOOTER+'</body>')
        if '<body>' in l:
            #~ import ipdb;ipdb.set_trace();print 'in ipdb!'
            l=l.replace('<body>', '<body>'+settings.HEADER)

        if l.startswith('<p>tags:'):
            out.write(linksection)
            out.write(tagsection)
            continue
        out.write(l)

    out.close()
    return

def rst2htmlpath(rst):
    return rst.replace('.rst','.html').replace('\\','/')

def get_all_tags():
    conn = sqlite3.connect('tmpdb')
    c=conn.cursor()
    res=c.execute('''select tag from rst2tag''').fetchall()
    return [r[0] for r in res]

def make_tag_page(tag):
    rsts=tag2rsts(tag, exclude=[])
    res=make_link_section(rsts)
    htmlpath='%s/tags/%s.html'%(settings.HTTP_BASE, tag)
    out=open(htmlpath,'w')
    out.write(settings.TAGPAGE_PREFIX)
    out.write(res)


def fix_perms():
    cmd='chmod 755 .'
    os.system(cmd)
    cmd='chmod 644 *.html'
    os.system(cmd)
    cmd='chmod 644 *.css'
    os.system(cmd)

def main(base):
    rsts=full_relative_paths_to_rsts(base)
    dat=make_htmls(rsts)
    rstdata.update(dat)
    recreate_db()
    for rst in rsts:
        tags=get_tags(rst)
        add_tags_to_db(rst=rst, tags=tags)
    for rst in rsts:
        print rst
        tags=tags_from_db(rst)
        related_rsts=get_related_rsts(rst, tags)[:10]
        htmlpath=rst2htmlpath(rst)
        put_stuff_into_html(htmlpath, related_rsts, tags)
    alltags=get_all_tags()
    if settings.LINK_TO_TAG_PAGES:
        for tag in alltags:
            make_tag_page(tag)
    fix_perms()

if __name__=="__main__":
    if len(sys.argv)==1:
        base='.'
    else:
        base=sys.argv[-1]
    if not os.path.isdir(base):
        print 'bad base.',base
        sys.exit()
    main(base)