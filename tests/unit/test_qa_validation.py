"""Offline question schema/references, never retrieval accuracy or model scoring."""
import csv
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/eval/validate_qa.py'
spec = importlib.util.spec_from_file_location('pr11_qa_validator', SCRIPT)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def question(**updates):
    return {'id':'qa-001','question':'合成结构测试问题？','series':'shl','gold_video_id':'shl-001',
            'gold_start_s':10.25,'gold_end_s':20.5,'tolerance_s':30,'gold_kp_id':'shl-001.kp0001',
            'tags':['合成'],'notes':'synthetic only', **updates}


@pytest.fixture
def inputs(tmp_path):
    knowledge = tmp_path / 'data/knowledge'
    lecture = knowledge / 'shl-001'
    lecture.mkdir(parents=True)
    index = knowledge / '_index/knowledge_points.csv'
    index.parent.mkdir()
    with index.open('w') as f:
        writer = csv.DictWriter(f, fieldnames=['kp_id','video_id','start_s','end_s'])
        writer.writeheader()
        writer.writerow({'kp_id':'shl-001.kp0001','video_id':'shl-001','start_s':10.25,'end_s':20.5})
    kp = {'kp_id':'shl-001.kp0001','video_id':'shl-001','start_s':10.25,'end_s':20.5,
          'citation':{'youtube_id':'W-z7WGZXmp8','url':'https://www.youtube.com/watch?v=W-z7WGZXmp8&t=10s',
                      'series':'shl','episode':1,'start_s':10.25,'end_s':20.5}}
    native = lecture / 'knowledge_points.jsonl'
    native.write_text(json.dumps(kp)+'\n')
    catalog=tmp_path/'web/src/data/lectures.json'
    catalog.parent.mkdir(parents=True)
    catalog.write_text(json.dumps({'lectures':[{'id':'shl-001','youtubeId':'W-z7WGZXmp8'}]}))
    qa = tmp_path / 'qa.jsonl'
    qa.write_text(json.dumps(question())+'\n')
    return qa, knowledge, index, native


@pytest.mark.parametrize('change', ['empty','nonfinite','boolean'])
def test_legacy_cli_must_not_accept_empty_or_invalid_numeric_values(inputs, monkeypatch, change):
    qa, knowledge, index, native = inputs
    if change == 'empty':
        qa.write_text('# no actual questions\n\n')
    else:
        # No KP means the old script's float(NaN/True) gap is exercised, not a mismatch.
        q = question(gold_start_s=float('nan') if change == 'nonfinite' else True)
        q.pop('gold_kp_id')
        qa.write_text(json.dumps(q)+'\n')
    monkeypatch.setattr(validator, 'REPO', qa.parent)
    monkeypatch.setattr(sys, 'argv', [str(SCRIPT), '--path', str(qa)])
    assert validator.main() != 0


def run_report(inputs, strict=True):
    qa, knowledge, index, _ = inputs
    return validator.validate_qa(qa, knowledge, index, strict_kp=strict)


def test_valid_report_is_stable_and_not_a_score(inputs):
    report = run_report(inputs)
    assert report == run_report(inputs)
    assert report['schema'] == 'qa-validation/1' and report['ok'] is True
    assert report['counts']['records'] == report['counts']['valid_records'] == 1
    assert report['answer_quality'] == 'not_evaluated' and report['retrieval_metrics'] is None
    assert report['counts']['kp_references'] == 1 and report['errors'] == []
    assert all(len(i['sha256']) == 64 for i in report['inputs'])


@pytest.mark.parametrize('field,value', [
    ('id',''), ('id',[]), ('question','  '), ('question',False), ('series',None),
    ('gold_video_id','../outside'), ('gold_video_id','shl-999'), ('series','jgy'),
    ('gold_kp_id',None), ('gold_kp_id',['shl-001.kp0001']), ('gold_kp_id','jgy-001.kp0001'),
    ('gold_kp_id','shl-001.kp9999'), ('gold_start_s',-1), ('gold_start_s',True),
    ('gold_start_s','10.25'), ('gold_start_s',21), ('gold_end_s',9),
    ('tolerance_s',-1), ('tolerance_s',False), ('tags','one tag'), ('tags',[None]),
    ('notes',{}), ('citations', [{'video_id':'shl-001'}]),
])
def test_bad_fields_fail_with_physical_line_and_field(inputs,field,value):
    inputs[0].write_text('# comment\n\n'+json.dumps(question(**{field:value}))+'\n')
    report=run_report(inputs)
    assert not report['ok'] and report['exit_code'] != 0
    expected_field='gold_end_s' if field=='gold_start_s' and value==21 else field
    assert any(e['line']==3 and e['field']==expected_field for e in report['errors']), report


def test_required_fields_and_duplicate_ids_keep_actual_jsonl_line_numbers(inputs):
    qa=inputs[0]
    bad=question();bad.pop('question')
    qa.write_text(json.dumps(question())+'\n# note\n\n'+json.dumps(question())+'\n'+json.dumps(bad)+'\n')
    errors=run_report(inputs)['errors']
    assert any(e['line']==4 and e['field']=='id' and e['code']=='duplicate_id' for e in errors)
    assert any(e['line']==5 and e['field']=='question' for e in errors)


@pytest.mark.parametrize('raw', ['{','null','[]','123','{"id":"qa-001","id":"qa-002"}',
    json.dumps(question()).replace('10.25','NaN'),json.dumps(question()).replace('10.25','1e999')])
def test_bad_json_shapes_nonfinite_and_duplicate_keys_are_reports_not_tracebacks(inputs,raw):
    inputs[0].write_text(raw+'\n')
    report=run_report(inputs)
    assert not report['ok'] and report['errors'][0]['line']==1


def test_empty_and_missing_file_never_pass(inputs):
    qa=inputs[0];qa.write_text(' \n# comments only\n')
    assert run_report(inputs)['counts']['records']==0 and not run_report(inputs)['ok']
    qa.unlink();report=run_report(inputs)
    assert report['exit_code']==2 and report['errors'][0]['code']=='missing_input'


def test_video_only_is_explicitly_partial_and_ci_strict_mode_rejects_it(inputs):
    q=question();q.pop('gold_kp_id');inputs[0].write_text(json.dumps(q)+'\n')
    partial=run_report(inputs,strict=False)
    assert partial['ok'] and partial['counts']['video_only_references']==1
    assert not run_report(inputs,strict=True)['ok']


@pytest.mark.parametrize('change', ['missing_citation','wrong_video','wrong_series','wrong_episode','bad_cite_time','wrong_url','wrong_url_time','ambiguous_url_time','wrong_but_consistent_youtube','missing_native','duplicate_native'])
def test_native_reference_identity_citation_and_time_are_checked_not_only_csv(inputs,change):
    native=inputs[3];kp=json.loads(native.read_text())
    if change=='missing_citation': kp.pop('citation')
    elif change=='wrong_video':kp['video_id']='jgy-001'
    elif change=='wrong_series':kp['citation']['series']='jgy'
    elif change=='wrong_episode':kp['citation']['episode']=True
    elif change=='bad_cite_time':kp['citation']['end_s']=400
    elif change=='wrong_url':kp['citation']['url']='https://evil.example/watch?v=W-z7WGZXmp8'
    if change=='wrong_url_time':kp['citation']['url']='https://www.youtube.com/watch?v=W-z7WGZXmp8&t=999s'
    if change=='ambiguous_url_time':kp['citation']['url']='https://www.youtube.com/watch?v=W-z7WGZXmp8&t=10&t=999'
    if change=='wrong_but_consistent_youtube':
        kp['citation']['youtube_id']='IH3tubhWMOo';kp['citation']['url']='https://www.youtube.com/watch?v=IH3tubhWMOo'
    if change=='missing_native':native.unlink()
    else:native.write_text(json.dumps(kp)+'\n'+(json.dumps(kp)+'\n' if change=='duplicate_native' else ''))
    report=run_report(inputs)
    assert not report['ok'] and any(e['field']=='gold_kp_id' and e['line']==1 for e in report['errors'])


def test_rounded_citation_and_index_tolerance_does_not_use_question_tolerance_to_hide_errors(inputs):
    native=inputs[3];kp=json.loads(native.read_text());kp['citation']['end_s']=20.55
    native.write_text(json.dumps(kp)+'\n');assert run_report(inputs)['ok']
    q=question(gold_end_s=20.56,tolerance_s=999999);inputs[0].write_text(json.dumps(q)+'\n')
    assert not run_report(inputs)['ok']


def test_index_missing_duplicates_and_bad_times_do_not_silently_override(inputs):
    index=inputs[2];text=index.read_text();index.write_text(text+text.splitlines()[1]+'\n')
    assert any(e['field']=='kp_id' and e['code']=='duplicate_kp' for e in run_report(inputs)['errors'])
    index.write_text(text.replace('20.5','nan'));assert not run_report(inputs)['ok']
    index.unlink();assert run_report(inputs)['exit_code']==2


def test_two_questions_can_cite_one_kp_but_multiple_gold_ids_are_not_this_schema(inputs):
    qa=inputs[0];qa.write_text(json.dumps(question())+'\n'+json.dumps(question(id='qa-002'))+'\n')
    report=run_report(inputs);assert report['ok'] and report['counts']['kp_references']==2 and report['counts']['unique_kps']==1


def test_unsafe_symlink_and_missing_knowledge_root_do_not_read_arbitrary_paths(inputs,tmp_path):
    qa,knowledge,index,native=inputs
    native.unlink();native.parent.rmdir();outside=tmp_path/'outside';outside.mkdir();native.parent.symlink_to(outside,target_is_directory=True)
    report=run_report(inputs);assert not report['ok'] and any(e['field']=='gold_video_id' for e in report['errors'])
    report=validator.validate_qa(qa,tmp_path/'absent',index,strict_kp=True)
    assert report['exit_code']==2


def test_real_tracked_fifty_baseline_is_immutable_and_all_references_pass():
    import hashlib
    qa=ROOT/'eval/retrieval/qa.jsonl'
    assert hashlib.sha256(qa.read_bytes()).hexdigest()=='dc83fcc9cbf97c9ffd8d8bfb67e0480e2420dcdbad3684492d5b51515edf3097'
    report=validator.validate_qa(qa,ROOT/'data/knowledge',ROOT/'data/knowledge/_index/knowledge_points.csv',strict_kp=True)
    assert report['ok'], report['errors']
    assert report['counts']['records']==report['counts']['valid_records']==report['counts']['kp_references']==50


def test_cli_json_is_stable_independent_of_cwd_and_bad_input_is_nonzero(inputs,tmp_path):
    import subprocess
    command=[sys.executable,str(SCRIPT),'--path',str(inputs[0]),'--knowledge-root',str(inputs[1]),'--index',str(inputs[2]),'--strict-kp','--json']
    a=subprocess.run(command,cwd=tmp_path,capture_output=True,text=True)
    b=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
    assert a.returncode==b.returncode==0 and a.stdout==b.stdout and not a.stderr
    assert json.loads(a.stdout)['answer_quality']=='not_evaluated'
    inputs[0].write_text('{\n');bad=subprocess.run(command,cwd=tmp_path,capture_output=True,text=True)
    assert bad.returncode==1 and json.loads(bad.stdout)['errors'][0]['line']==1 and 'Traceback' not in bad.stderr


@pytest.mark.parametrize('change', ['missing_catalog','empty_catalog','duplicate_catalog','bad_utf8','empty_index','bad_header'])
def test_required_input_integrity_is_not_silently_filtered(inputs,tmp_path,change):
    qa,knowledge,index,native=inputs
    catalog=tmp_path/'web/src/data/lectures.json'
    if change=='missing_catalog':catalog.unlink()
    elif change=='empty_catalog':catalog.write_text('{"lectures":[]}')
    elif change=='duplicate_catalog':
        value=json.loads(catalog.read_text());value['lectures']*=2;catalog.write_text(json.dumps(value))
    elif change=='bad_utf8':qa.write_bytes(b'\xff\xfe\n')
    elif change=='empty_index':index.write_text('kp_id,video_id,start_s,end_s\n')
    elif change=='bad_header':index.write_text('kp_id,kp_id,start_s,end_s\n')
    report=validator.validate_qa(qa,knowledge,index,strict_kp=True,catalog_path=catalog)
    assert not report['ok'] and report['exit_code']!=0 and report['errors']


def test_referenced_source_file_json_error_is_not_hidden_by_valid_csv(inputs):
    inputs[3].write_text('{\n')
    report=run_report(inputs)
    assert not report['ok']
    assert any(e['line']==1 and e['field']=='$' and e['code']=='invalid_json' for e in report['errors'])
    assert any(e['field']=='gold_kp_id' for e in report['errors'])


def test_reports_source_hash_changes_and_never_rewrites_any_input(inputs):
    files=list(inputs);before={p:p.read_bytes() for p in files if p.is_file()}
    first=run_report(inputs);inputs[3].write_text(inputs[3].read_text()+'\n')
    second=run_report(inputs)
    assert first['ok'] and second['ok'] and first['inputs']!=second['inputs']
    assert all(p.read_bytes()==raw for p,raw in before.items() if p!=inputs[3])
    assert inputs[3].read_bytes()==before[inputs[3]]+b'\n'


def test_malformed_index_csv_locates_the_actual_source_line(inputs):
    inputs[2].write_text('kp_id,video_id,start_s,end_s\n"unfinished\n')
    report=run_report(inputs)
    assert any(e['code']=='invalid_csv' and e['line']==2 and e['field']=='$' for e in report['errors'])


def test_corrupt_shared_native_file_cannot_make_cached_later_references_look_valid(inputs):
    inputs[0].write_text(json.dumps(question())+'\n'+json.dumps(question(id='qa-002'))+'\n')
    inputs[3].write_text(inputs[3].read_text()+'{\n')
    report=run_report(inputs)
    assert not report['ok'] and report['counts']['valid_records']==0 and report['counts']['invalid_records']==2
    assert {e['line'] for e in report['errors'] if e['field']=='gold_kp_id'}=={1,2}
