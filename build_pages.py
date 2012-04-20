import sys, os, sqlite3, shutil, datetime, ipdb, re, time, random
from docutils import io
from docutils.utils import SystemMessage
from docutils.core import publish_cmdline, default_description, publish_programmatically

"""run python build_page.py base_path"""

class Bag:
    pass

settings=Bag()


st= {'HTTP_BASE':''}

st['GENLINK_PREFIX']='<h2>Related Links</h2>'
st['GENTAG_PREFIX']='<h2>Tags</h2>'
st['DEST_BASE']='d:/proj/rst/'
local=True
if os.path.exists('setup/live'):
    local=False
    st['HTTP_BASE']='/home'
    st['DEST_BASE']='/home/ernop/fuseki.net/public/home/'
if os.path.exists('setup/work'):
    local=True
    st['HTTP_BASE']=''
    st['DEST_BASE']='/home/ernie/ernop/home/'
if os.path.exists('setup/home'):
    local=True
    st['HTTP_BASE']=''
    st['DEST_BASE']='/home/ernie/proj/home/'

st['TAGPAGE_PREFIX']='<h1>Tag page for "%s"</h1>'

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
            #~ fx=settings.DEST_BASE[0].upper()+settings.DEST_BASE[1:]
            if settings.DEST_BASE in s:
                s=s.replace(settings.DEST_BASE,'/')
            if 'http:/' in s:
                a,b=s.split('http:/',1)
                a=a.rsplit('"',1)[0]+'"'
                s=a+'http://'+b
            newlinks.append(s)
        self.stylesheet=newlinks

    def add_extra_head(self):
        self.head.append('<meta name="viewport" content="width=device-width" />\n')

class MyWriter(Writer):
    def translate(self):
        self.visitor = visitor = MyHTMLTranslator(self.document)
        self.visitor.fix_style_links()
        self.visitor.add_extra_head()
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
        except SystemMessage, e:
            print 'problem with:',rst,e
            import ipdb;ipdb.set_trace();print 'in ipdb!'
        except Exception, e:
            print 'other problem!',e
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
    #tags.append(random.choice(['_a','_b','_c','_d']))
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
    res=sorted([r[0] for r in res if r[0] not in exclude], key=lambda x:rstdata[x]['title'])
    return res

def get_related_rsts(rst, tags_and_weights):
    """ordered by weight."""
    res={}
    for tag, weight in tags_and_weights:
        rsts=tag2rsts(tag, exclude=rst)
        for subrst in rsts:
            res[subrst]=res.get(subrst,0)+(1.0/weight)
    return [_[0] for _ in sorted(list(res.items()), key=lambda x:-1*x[1])]


def rst2link(rst, page=False):
    htmlpath='%s/%s'%(settings.HTTP_BASE,rst2html(rst))
    if rst in rstdata:
        title=rstdata[rst]['title']
    else:
        title=rst.replace(".rsx",'').replace('-',' ').title()
    if page:
        pt='<a href="%s">%s</a>'%(htmlpath, title)
    else:
        pt='<span class="genlink"><a href="%s">%s</a></span>'%(htmlpath, title)
    return pt

def make_link_section(rsts):
    res=[]
    for rst in rsts:
        fn=os.path.split(rst)[1]
        pt=rst2link(rst)
        res.append(pt)
        #res.sort(key=lambda x:x.split('</a>',1)[0].rsplit("\">",1)[-1])
    res='<span class="genlink_section">%s%s</span>'%(settings.GENLINK_PREFIX, ''.join(res))
    return res

def tag2link(tag, count=None):
    taglink='%s/tags/%s.html'%(settings.HTTP_BASE, tag2urlsafe(tag))
    if count:
        pt='<div class="gentag"><a href="%s">%s (%d)</a></div>'%(taglink, tag, count)
    else:
        pt='<div class="gentag"><a href="%s">%s</a></div>'%(taglink, tag)

    return pt

def make_tag_section(tags):
    res=[]
    for tag in tags:
        if tag.startswith('_'):continue
        link=len(tag2rsts(tag, exclude=[]))>1
        #it is definitely wrong to get this here when you're already getting it later to make the actual tag pages.
        if link:
            pt=tag2link(tag)
        else:
            pt='<div class="gentag">%s</div>'%(tag)
        res.append(pt)
    res='<div class="gentag_section">%s%s</div>'%(settings.GENTAG_PREFIX, ''.join(res))
    return res


def linktext2rst(linktext):
    rawtext=linktext.strip('[]').lower()
    dashed=linktext.strip('[]').lower().replace(' ','-')
    matches=[]
    for k in rstdata.keys():
        if dashed in k:
            matches.append(k)
    for k,vals in rstdata.items():
        if rawtext in vals['title'].lower():
            if k not in matches:
                matches.append(k)
    if not matches:
        print 'ERROR, no link found for %s'%linktext
        import ipdb;ipdb.set_trace()
        return None
    if len(matches)>1:
        matches.sort(key=lambda x:len(x))
        print 'ERROR, multiple matches for linktext %s, %s'%(linktext,matches)
        import ipdb;ipdb.set_trace()
    return matches[0]

def put_stuff_into_html(htmlpath, html, related_rsts, tags, moddate):
    assert htmlpath.endswith('.html')
    if not htmlpath.endswith('.html'):
        import ipdb;ipdb.set_trace();print 'in ipdb!'
    if not os.path.exists(htmlpath):
        import ipdb;ipdb.set_trace();print 'in ipdb!'
    lines=open(htmlpath,'r').readlines()
    linksection=make_link_section(related_rsts)
    tagsection=make_tag_section(tags)
    out=open(htmlpath,'w')
    foot=mkfoot(moddate)
    linkre=re.compile(r'(?P<linkname>\[[^\]\[]+\])')
    for l in lines:
        if '</body>' in l:
            l=l.replace('</body>', foot +'</body>')
        if '<body>' in l:
            l=l.replace('<body>', '<body>'+settings.HEADER+'<div class="article">')
        links=linkre.findall(l)
        if links and 'bookmarklet' not in htmlpath:
            for txt in links:
                target_rst=linktext2rst(txt)
                if not target_rst:
                    continue
                target_link=rst2link(target_rst, page=True)
                if target_link:
                    l=l.replace(txt,target_link)
        if '<p>tags:' in l:
            pt=l.split('<p>tags',1)
            out.write(pt[0])
            #gotta keep the first part.

            out.write('</div></div></div></div></div><div class="genblock">')
            #when we have multiple h2s, somehow 2 </divs> is not enough - we're still in body.  so put 3 and restyle genblock same as article.
            out.write(tagsection)
            out.write(linksection)
            if local:
                localsection='<p><a href=http://fuseki.net/home/%s>live link</a>'%(htmlpath.rsplit('/',1)[-1])
                out.write(localsection)
            out.write('</div>')
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

def getblank(destpath):
    rst='_blank.rsx'
    if not os.path.exists(rst):
        os.system('touch %s'%rst)
    pub=publish_file(source_path=rst, destination_path=destpath, settings_overrides=settings_overrides)
    return pub

def make_tag_page(tag):
    rsts=tag2rsts(tag, exclude=[])
    if len(rsts)<=1:
        return 0
    print '%s (%d)'%(tag, len(rsts)),
    res=make_link_section(rsts)
    destpath='%stags/%s.html'%(settings.DEST_BASE, tag2urlsafe(tag))
    getblank(destpath)
    lines=open(destpath,'r').readlines()
    out=open(destpath,'w')
    foot=settings.TAG_FOOTER
    for l in lines:
        if '<title>' in l:
            l=l.replace('<title>','<title>Tag Page for %s'%tag)
        if 'class="document">' in l:
            fxd=l.replace('class="document">','class="document"><div class="article">%s%s</div>%s'%(settings.TAGPAGE_PREFIX%tag,res, foot))
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
    #~ try:
        #~ cmd='chmod 644 *.html'
        #~ os.system(cmd)
    #~ except:
        #~ pass
    try:
        cmd='chmod 644 *.css'
        os.system(cmd)
    except:
        pass


def mkfoot(moddate):
    foot=settings.FOOTER%datetime.datetime.strftime(datetime.datetime.fromtimestamp(moddate), '%Y-%m-%d')
    return foot

def make_all_tags_page(tagcounts):
    destpath='%s/tags/index.html'%(settings.DEST_BASE)
    getblank(destpath)
    lines=open(destpath,'r').readlines()
    out=open(destpath,'w')
    foot=settings.TAG_FOOTER
    res=''
    for tag,count  in sorted(tagcounts.items(),key=lambda x:(-1*x[1],x[0])):
        if tag.startswith('_'):
            continue
        if count>1:
            res+=tag2link(tag, count)
    for l in lines:
        if '<title>' in l:
            l=l.replace('<title>','<title>All Tags')
        if 'class="document">' in l:
            fxd=l.replace('class="document">','class="document"><div class="article"><h1>All tags</h1> %s</div>%s'%(res, foot))
            out.write(fxd)
        else:
            out.write(l)

def make_all_pages_page():
    destpath='%s/all_pages.html'%(settings.DEST_BASE)
    getblank(destpath)
    lines=open(destpath,'r').readlines()
    out=open(destpath,'w')
    foot=settings.FOOTER
    res=''
    rsts=[_[0] for _ in sorted([(k[0],k[1]['title']) for k in rstdata.items()], key=lambda x:x[1])]
    linksection=make_link_section(rsts)
    out=open(destpath,'w')
    foot=mkfoot(time.time())
    linkre=re.compile(r'(?P<linkname>\[[^\]\[]+\])')
    for l in lines:
        if '</body>' in l:
            l=l.replace('</body>', linksection+foot +'</body>')
        if '<body>' in l:
            l=l.replace('<body>', '<body>'+settings.HEADER+'<div class="article"><h1>All Pages</h1>')
        if '<p>tags:' in l and 0:
            pt=l.split('<p>tags',1)
            out.write(pt[0])
            #gotta keep the first part.

            out.write('</div></div></div></div></div><div class="genblock">')
            #when we have multiple h2s, somehow 2 </divs> is not enough - we're still in body.  so put 3 and restyle genblock same as article.
            out.write(tagsection)
            out.write(linksection)
            if local:
                localsection='<p><a href=http://fuseki.net/home/%s>live link</a>'%(destpath.rsplit('/',1)[-1])
                out.write(localsection)
            out.write('</div>')
            continue
        out.write(l)
    out.close()

def make_all_rsx_pages():
    destpath='%s/all_rsx.html'%(settings.DEST_BASE)
    getblank(destpath)
    lines=open(destpath,'r').readlines()
    out=open(destpath,'w')
    foot=settings.FOOTER
    res=''
    rsts=[r for r in os.listdir('.') if r.endswith('rsx')]
    linksection=make_link_section(rsts)
    out=open(destpath,'w')
    foot=mkfoot(time.time())
    linkre=re.compile(r'(?P<linkname>\[[^\]\[]+\])')
    for l in lines:
        if '</body>' in l:
            l=l.replace('</body>', linksection+foot +'</body>')
        if '<body>' in l:
            l=l.replace('<body>', '<body>'+settings.HEADER+'<div class="article"><h1>All RSXs</h1>')
        out.write(l)
    out.close()

def main(base):
    rsts=full_relative_paths_to_rsts(base)
    if todo.some=='1':
        rsts=rsts[:5]
    if todo.some:
        rsts=[r for r in rsts if 'index-test' in r]
    dat=make_htmls(rsts)
    rstdata.update(dat)
    recreate_db()
    rsts.sort()
    for ii,rst in enumerate(rsts):
        print rst[2:].replace('.rst',''),
        tags=get_tags(rst)
        if not tags:
            print 'ERROR, rst has no tags. %s'%rst
        for t in tags:
            if t.lower()!=t:
                print 'ERROR in tag: %s, not lowercase. %s'%(t, rst)
        add_tags_to_db(rst=rst, tags=tags)
    print ''
    alltags=get_all_tags()
    for rst in rsts:
        tags=tags_from_db(rst)
        tags_and_weights=sorted([(tag, alltags[tag]) for tag in tags], key=lambda x:x[1])
        related_rsts=get_related_rsts(rst, tags_and_weights)[:10]
        htmlpath=rst2htmlpath(rst)
        put_stuff_into_html(htmlpath, rst2html(rst), related_rsts, tags, os.stat(rst).st_mtime)
    tagdir=os.path.join(settings.DEST_BASE,'tags')
    if not os.path.exists(tagdir):
        os.makedirs(tagdir)
    tagcounts={}
    for tag in sorted(alltags.keys()):
        tagcounts[tag]=make_tag_page(tag)
    make_all_tags_page(tagcounts)
    make_all_pages_page()
    make_all_rsx_pages()
    fix_perms()

import argparse
parser = argparse.ArgumentParser(description='')
parser.add_argument('--some','-s',
    dest='some',
    action='store_const',
    const=True,
    default=None,
    )

parser.add_argument('--base', '-b',dest='base', default='.',
                   help='base dir to look in.')

todo = parser.parse_known_args()[0]


if __name__=="__main__":
    if not os.path.isdir(todo.base):
        print 'bad base.',base
        sys.exit()
    main(todo.base)
