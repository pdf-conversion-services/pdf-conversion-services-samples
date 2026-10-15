"""Build unbranded interactive PDFs and validate their AcroForm data.
Run: python build_samples.py [--render]
Rendering requires pdftoppm on PATH. Filled PDFs are temporary verification files.
"""
from pathlib import Path
import argparse, json, subprocess, tempfile
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4, letter
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / 'repository.json').read_text(encoding='utf-8'))
NAVY, TEAL, MUTED, LINE = map(HexColor, ['#142B43','#087F8C','#58687A','#C7D5E1'])
REGIONS = {
    'us': dict(name='United States', size=letter, paper='US Letter', date='MM/DD/YYYY', day='10/15/2026', region='State', postal='ZIP code', city='New York', area='NY', code='10001'),
    'uk': dict(name='United Kingdom', size=A4, paper='A4', date='DD/MM/YYYY', day='15/10/2026', region='County / region', postal='Postcode', city='London', area='Greater London', code='SW1A 1AA'),
    'au': dict(name='Australia', size=A4, paper='A4', date='DD/MM/YYYY', day='15/10/2026', region='State / territory', postal='Postcode', city='Sydney', area='NSW', code='2000'),
}

def make_form(code, dest):
    reg = REGIONS[code]
    w,h = reg['size']
    c = canvas.Canvas(str(dest), pagesize=(w,h))
    c.setTitle(CONFIG['form'] + ' - ' + reg['name'])
    c.setAuthor('')
    c.setSubject('Unbranded interactive sample template')
    c.setFillColor(NAVY); c.rect(0,h-128,w,128,fill=1,stroke=0)
    c.setFillColor(HexColor('#6ED9D0')); c.setFont('Helvetica-Bold',9)
    c.drawString(40,h-38,'INTERACTIVE PDF / SAMPLE TEMPLATE')
    c.setFillColor(white); c.setFont('Helvetica-Bold',25)
    c.drawString(40,h-76,CONFIG['form'])
    c.setFont('Helvetica',10)
    c.drawString(40,h-101,reg['name']+'  |  '+reg['paper']+'  |  Date: '+reg['date'])
    c.setFillColor(MUTED); c.setFont('Helvetica',9)
    c.drawString(40,h-150,'Save a copy, complete the fields and review before sharing.')
    content = w-80; half=(content-16)/2; third=(content-24)/3
    y=h-180
    schema={}; values={}
    def section(title):
        nonlocal y
        c.setFillColor(TEAL); c.setFont('Helvetica-Bold',10)
        c.drawString(40,y,title.upper())
        c.setStrokeColor(LINE); c.line(40,y-8,w-40,y-8)
        y-=35
    def field(name,label,x,top,width,value,options=None,height=27,multi=False):
        c.setFillColor(MUTED); c.setFont('Helvetica',8.5); c.drawString(x,top,label)
        params=dict(name=name,tooltip=label,x=x,y=top-height-8,width=width,height=height,
                    borderWidth=.65,borderColor=LINE,fillColor=HexColor('#F4F8FC'),textColor=NAVY,
                    fontName='Helvetica',fontSize=10,forceBorder=True,value='')
        if options:
            params['value']=options[0]
            c.acroForm.choice(**params,options=options,fieldFlags='combo')
        else:
            c.acroForm.textfield(**params,fieldFlags='multiline' if multi else '',maxlen=260 if multi else 80)
        schema[name]=dict(label=label,type='choice' if options else 'text',options=options)
        values[name]=value
    def row(items):
        nonlocal y
        count=len(items); gap=16; width=(content-gap*(count-1))/count
        for i,(name,label,value,*opts) in enumerate(items):
            field(name,label,40+i*(width+gap),y,width,value,opts[0] if opts else None)
        y-=62
    def area(name,label,value,height=65):
        nonlocal y
        field(name,label,40,y,content,value,height=height,multi=True); y-=height+35
    def check(name,label):
        nonlocal y
        c.acroForm.checkbox(name=name,tooltip=label,x=40,y=y-13,size=13,buttonStyle='check',
                            borderWidth=.7,borderColor=LINE,fillColor=white,textColor=TEAL,checked=False)
        c.setFillColor(NAVY); c.setFont('Helvetica',9); c.drawString(61,y-10,label)
        schema[name]=dict(label=label,type='checkbox'); values[name]='/Yes'; y-=27
    kind=CONFIG['kind']
    if kind=='intake':
        section('01 / Contact details')
        row([('full_name','Full name','Alex Morgan'),('email','Email','alex@example.com')])
        row([('city','City',reg['city']),('region',reg['region'],reg['area']),('postal',reg['postal'],reg['code'])])
        section('02 / Project brief')
        row([('project','Project title','Community workshop registration'),('purpose','Form purpose','Registration',['Select a purpose','Registration','Client intake','Service request','Other'])])
        row([('date','Requested date ('+reg['date']+')',reg['day']),('contact_method','Preferred contact','Email',['Select a method','Email','Telephone'])])
        area('requirements','Fields or workflow needed','Collect participant name, email and session preference.\nReturn a completed copy for review.',58)
        check('reviewed','I have reviewed the details entered in this sample.')
    elif kind=='conversion':
        section('01 / Request details')
        row([('full_name','Contact name','Alex Morgan'),('email','Email','alex@example.com')])
        row([('source','Source format','Scanned PDF',['Select source','Digital PDF','Scanned PDF','Image files']),('target','Target format','DOCX',['Select target','DOCX','XLSX','PPTX','Searchable PDF'])])
        section('02 / Conversion requirements')
        row([('files','Estimated files','12'),('pages','Estimated pages','240'),('date','Needed by ('+reg['date']+')',reg['day'])])
        row([('layout','Layout priority','Editable content',['Select priority','Editable content','Match source layout','Extract tables']),('sample','Sample filename','workshop-notes-001.pdf')])
        area('instructions','Instructions and acceptance criteria','Preserve headings and tables. Check reading order.\nReview one converted file before processing the batch.',58)
        check('ocr','OCR is needed for scanned text.')
    else:
        section('01 / Batch specification')
        row([('batch','Batch reference','BATCH-001'),('date','Review date ('+reg['date']+')',reg['day'])])
        row([('target','Output format','Searchable PDF',['Select output','Searchable PDF','DOCX','XLSX','Mixed outputs']),('language','OCR language(s)','English')])
        section('02 / Representative inventory')
        for n in range(1,4):
            row([(f'file_{n}','Source file / group '+str(n),f'workshop-{n:03}.pdf'),(f'pages_{n}','Pages',str(n*10)),(f'result_{n}','Output filename',f'workshop-{n:03}-searchable.pdf')])
        area('acceptance','Naming rules and acceptance criteria','Keep original sequence. Use batch-reference + file number.\nCheck searchable text and page counts before handover.',45)
        check('inventory_checked','I have checked the inventory against the source files.')
    assert y >= 72, ('content overlaps footer',y)
    c.setStrokeColor(LINE); c.line(40,60,w-40,60)
    c.setFillColor(MUTED); c.setFont('Helvetica',8)
    c.drawString(40,44,'Sample only. No automatic submission or digital signature.'); c.drawRightString(w-40,44,'01 / 01')
    c.showPage(); c.save()
    return schema,values

def validate(path,expected=None):
    reader=PdfReader(path); fields=reader.get_fields() or {}
    assert fields, 'Missing canonical field tree'
    if expected is not None: assert set(fields)==set(expected)
    names=[]
    for page in reader.pages:
        for ref in page.get('/Annots',[]):
            widget=ref.get_object()
            if widget.get('/Subtype')!='/Widget': continue
            effective=widget
            while '/T' not in effective and '/Parent' in effective: effective=effective['/Parent'].get_object()
            name=str(effective['/T']); names.append(name)
            assert name in fields
            actual=widget.get('/V',effective.get('/V',''))
            assert str(actual)==str(fields[name].get('/V','')), ('Widget/canonical mismatch',name)
            if expected is not None: assert str(actual)==expected[name], (name,actual,expected[name])
            assert widget.get('/AP') and widget['/AP'].get('/N') is not None, ('Missing appearance',name)
            if fields[name]['/FT']=='/Btn':
                assert str(widget.get('/AS'))==str(actual)
                assert actual in widget['/AP']['/N']
    assert set(names)==set(fields) and len(names)==len(set(names)), 'Missing or duplicate widgets'
    return len(fields)

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--render',action='store_true'); args=parser.parse_args()
    report=[]; all_schema={}
    with tempfile.TemporaryDirectory() as tmp:
        for code,region in REGIONS.items():
            blank=ROOT/f"{CONFIG['kind']}-{code}-fillable.pdf"
            schema,values=make_form(code,blank); count=validate(blank)
            reader=PdfReader(blank); writer=PdfWriter(); writer.clone_document_from_reader(reader)
            writer.update_page_form_field_values(None,values,auto_regenerate=False)
            filled=Path(tmp)/f'{code}-filled.pdf'
            with filled.open('wb') as stream: writer.write(stream)
            validate(filled,values)
            if args.render:
                dest=ROOT/f"{CONFIG['kind']}-{code}-filled"
                subprocess.run(['pdftoppm','-r','110','-singlefile','-png',str(filled),str(dest)],check=True,capture_output=True)
                dest_blank=ROOT/f"{CONFIG['kind']}-{code}-blank"
                subprocess.run(['pdftoppm','-r','110','-singlefile','-png',str(blank),str(dest_blank)],check=True,capture_output=True)
            all_schema[code]=schema
            report.append(dict(country=region['name'],paper=region['paper'],fields=count,canonical_tree='pass',widgets='pass',fill_save_reopen='pass',appearance_streams='pass'))
    (ROOT/'field-schema.json').write_text(json.dumps(all_schema,indent=2)+'\n',encoding='utf-8')
    (ROOT/'validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(CONFIG['slug'],report)

if __name__=='__main__': main()
