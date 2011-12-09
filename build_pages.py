import sys, os, sqlite3, shutil, datetime
from docutils import io
from docutils.utils import SystemMessage
from docutils.core import publish_cmdline, default_description, publish_programmatically

"""run python build_page.py base_path"""

class Bag:
    pass

settings=Bag()


st= {'HTTP_BASE':''}

st['GENLINK_PREFIX']='<div class="genlink_prefix h2">Related Links</div>'
st['GENTAG_PREFIX']='<div class="gentag_prefix h2">Tags</div>'
st['DEST_BASE']='d:/proj/rst/'
if os.path.exists('setup/live'):
    st['HTTP_BASE']='/home'
    st['DEST_BASE']='/home/ernop/fuseki.net/public/home/'
st['TAGPAGE_PREFIX']='<div class="header">Tag page for "%s"</div>'

settings.__dict__.update(st)
MUST_EXIST=['header','footer','tag_footer']
for f in MUST_EXIST:
    fn='setup/'+f+'.html'
    if not os.path.isfile(fn):
        print 'could not find file',fn
        sys.exit()
    setattr(settings, f.upper(), open(fn,'r').read())

rstdata={}
settings_overrides={'stylesheet_path':'html4css1.css,hpcss.css,http://fonts.googleapis.com/css?family=Vollkorn&subset=latin',
    'theme':'big-black',
    'embed_stylesheet':False,
    #~ 'template':'template.txt',
    #~ 'link_stylesheet':'',
    }

from docutils.writers.html4css1 import Writer, HTMLTranslator
#change mywriter to use a myhtmltranslator which fixes css so we can mix local links with remote links.
class MyHTMLTranslator(HTMLTranslator):
    def fix_style_links(self):
        newlinks=[]
        for s in self.stylesheet:
            #fix dumb drive letter capitalization...
            s=s.replace('D:','d:')
            #stupid.
            if settings.DEST_BASE in s and 'http:/' in s:
                ss=s.replace(settings.DEST_BASE,'').replace('http:/','http://').replace('&amp;','&')
                ss=ss

                newlinks.append(ss)
            else:
                newlinks.append(s)
        self.stylesheet=newlinks

class MyWriter(Writer):
    def translate(self):
        self.visitor = visitor = MyHTMLTranslator(self.document)
        self.visitor.fix_style_links()
        self.document.walkabout(visitor)

        for attr in self.visitor_attributes:
            setattr(self, attr, getattr(visitor, attr))
        self.output = self.apply_template()

def publish_file(source_path=None, destination_path=None,
                 settings_overrides=None
                 ):
    a=MyWriter()
    output, pub = publish_programmatically(
        source_class=io.FileInput, source=None,source_path=source_path,
        destination_class=io.FileOutput,destination=None,
        destination_path=destination_path,reader=None,
         reader_name='standalone',parser=None,
        parser_name='restructuredtext',writer=a,writer_name='html',
        settings=None, settings_spec=None,
        settings_overrides=settings_overrides,config_section=None, enable_exit_status=None)
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
            destpath=os.path.join(settings.DEST_BASE,destpath)

            pub=publish_file(source_path=rst, destination_path=destpath, settings_overrides=settings_overrides)
            dat[rst]={'title':pub.document.get('title')}
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
    conn = sqlite3.connect('setup/tmpdb')
    c=conn.cursor()

    for tag in tags:
        c.execute('''insert into rst2tag (rst, tag) values ("%s","%s") '''%(rst, tag))
    conn.commit()
    c.close()

def recreate_db():
    if os.path.exists('setup/tmpdb'):
        os.remove('setup/tmpdb')
    conn = sqlite3.connect('setup/tmpdb')
    c=conn.cursor()
    c.execute('''create table rst2tag
        (rst text,  tag text)''')
    conn.commit()
    c.close()

def tags_from_db(rst):
    conn = sqlite3.connect('setup/tmpdb')
    c=conn.cursor()
    res=c.execute('select tag as c from rst2tag where rst="%s"'%rst).fetchall()
    return sorted([r[0] for r in res])

def tag2rsts(tag, exclude=None):
    conn = sqlite3.connect('setup/tmpdb')
    c=conn.cursor()
    res=c.execute('select rst from rst2tag where tag="%s"'%tag).fetchall()
    res=[r[0] for r in res if r[0] not in exclude]
    return res

def get_related_rsts(rst, tags_and_weights):
    res={}
    for tag, weight in tags_and_weights:
        rsts=tag2rsts(tag, exclude=rst)
        for subrst in rsts:
            res[subrst]=res.get(subrst,0)+(1.0/weight)
    return [_[0] for _ in sorted(list(res.items()), key=lambda x:-1*x[1])]

def make_link_section(rsts):
    res=[]
    for rst in rsts:
        try:
            fn=os.path.split(rst)[1]
        except:
            import ipdb;ipdb.set_trace();print 'in ipdb!'
        try:
            title=rstdata[rst]['title']
            if title is None:
                title='no title %s'%rst
        except:
            title='TITLEMISSING %s'%rst
            import ipdb;ipdb.set_trace();print 'in ipdb!'
        htmlpath='%s/%s'%(settings.HTTP_BASE,rst2html(rst))
        pt='<div class="genlink"><a href="%s">%s</a></div>'%(htmlpath, title)
        res.append(pt)
    res='<div class="genlink_section">%s%s</div>'%(settings.GENLINK_PREFIX, ''.join(res))
    return res

def make_tag_section(tags):
    res=[]

    for tag in tags:
        link=len(tag2rsts(tag, exclude=[]))>1
        #it is definitely wrong to get this here when you're already getting it later to make the actual tag pages.
        taglink='%s/tags/%s.html'%(settings.HTTP_BASE, tag2urlsafe(tag))
        if link:
            pt='<div class="gentag"><a href="%s">%s</a></div>'%(taglink, tag)
        else:
            pt='<div class="gentag">%s</div>'%(tag)
        res.append(pt)
    res='<div class="gentag_section">%s%s</div>'%(settings.GENTAG_PREFIX, ''.join(res))
    return res

def put_stuff_into_html(htmlpath, html, related_rsts, tags):
    assert htmlpath.endswith('.html')
    if not htmlpath.endswith('.html'):
        import ipdb;ipdb.set_trace();print 'in ipdb!'
    if not os.path.exists(htmlpath):
        import ipdb;ipdb.set_trace();print 'in ipdb!'
    lines=open(htmlpath,'r').readlines()
    linksection=make_link_section(related_rsts)
    tagsection=make_tag_section(tags)
    out=open(htmlpath,'w')
    moddate=os.stat(htmlpath).st_mtime
    foot=settings.FOOTER%datetime.datetime.strftime(datetime.datetime.fromtimestamp(moddate), '%Y-%m-%d')
    for l in lines:
        if '</body>' in l:
            l=l.replace('</body>', foot +'</body>')
        if '<body>' in l:
            l=l.replace('<body>', '<body>'+settings.HEADER)

        if l.startswith('<p>tags:'):
            out.write(linksection)
            out.write(tagsection)
            continue
        out.write(l)

    out.close()
    return

def rst2htmlpath(rst):
    """the file path to it."""
    return os.path.join(settings.DEST_BASE,rst.replace('.rst','.html').replace('\\','/'))

def get_all_tags():
    conn = sqlite3.connect('setup/tmpdb')
    c=conn.cursor()
    res=c.execute('''select tag, count(*) from rst2tag group by 1 order by 2''').fetchall()
    return dict([(r[0],r[1]) for r in res])

def tag2urlsafe(tag):
    return tag.replace(' ','_')

def make_tag_page(tag):
    rsts=tag2rsts(tag, exclude=[])
    if len(rsts)<=1:
        return 0
    print 'tag %s, len %d'%(tag, len(rsts))
    res=make_link_section(rsts)
    rst='_blank.rst'
    if not os.path.exists(rst):
        os.system('touch %s'%rst)
    destpath='%s/tags/%s.html'%(settings.DEST_BASE, tag2urlsafe(tag))
    pub=publish_file(source_path=rst, destination_path=destpath, settings_overrides=settings_overrides)
    lines=open(destpath,'r').readlines()

    out=open(destpath,'w')
    foot=settings.TAG_FOOTER
    for l in lines:
        if 'class="document">' in l:
            fxd=l.replace('class="document">','class="document">%s%s%s'%(settings.TAGPAGE_PREFIX%tag,res, foot))
            out.write(fxd)
        else:
            out.write(l)
    return len(rsts)

def rst2html(rst):
    return rst.replace('.rst','.html').replace('\\','/')

def fix_perms():
    try:
        cmd='chmod 755 .'
        os.system(cmd)
    except:
        pass
    try:
        cmd='chmod 644 *.html'
        os.system(cmd)
    except:
        pass
    try:
        cmd='chmod 644 *.css'
        os.system(cmd)
    except:
        pass

def main(base):
    rsts=full_relative_paths_to_rsts(base)
    dat=make_htmls(rsts)
    rstdata.update(dat)
    recreate_db()
    for rst in rsts:
        print rst
        tags=get_tags(rst)
        add_tags_to_db(rst=rst, tags=tags)
    alltags=get_all_tags()
    for rst in rsts:
        tags=tags_from_db(rst)
        tags_and_weights=sorted([(tag, alltags[tag]) for tag in tags], key=lambda x:x[1])
        related_rsts=get_related_rsts(rst, tags_and_weights)[:10]
        htmlpath=rst2htmlpath(rst)
        put_stuff_into_html(htmlpath, rst2html(rst), related_rsts, tags)

    tagdir=os.path.join(settings.DEST_BASE,'tags')
    if not os.path.exists(tagdir):
        os.makedirs(tagdir)
    for tag in alltags.keys():
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