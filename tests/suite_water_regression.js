// ---- water regression dump: runs a non-trivial cold + hot job and prints every number the
// drawing depends on. Run against the committed build and the new one; the output must be
// byte-identical. Uses only APIs that exist in both.

function dump(label, v){ note(label+' = '+v); }

state.building={job:{name:'REGRESSION',number:'12345'},
  levels:['B1','GROUND','LEVEL 1','LEVEL 2','LEVEL 3','LEVEL 4','LEVEL 5','LEVEL 6','LEVEL 7','LEVEL 8'],
  groundIdx:1};

note('=== demand curves ===');
for(var n=1;n<=40;n+=3) dump('flowFromDwellings('+n+')', flowFromDwellings(n).toFixed(6));
for(var lu=1;lu<=400;lu+=37) dump('flowFromLU('+lu+')', flowFromLU(lu).toFixed(6));
for(var h=1;h<=110;h+=9) dump('hwFlowFromDwellings('+h+')', hwFlowFromDwellings(h).toFixed(6));

note('=== pipe selection sweep ===');
var mats=['copper_type_b','stainless_steel'], vels=[1.2,2.0,2.5];
for(var mi=0;mi<mats.length;mi++) for(var vi=0;vi<vels.length;vi++){
  var line=[];
  for(var q=0.05;q<=12;q*=1.7){
    var p=selectPipe(q,mats[mi],vels[vi]);
    line.push(q.toFixed(3)+':'+(p?p.DN:'X'));
  }
  dump('selectPipe '+mats[mi]+' @'+vels[vi], line.join(' '));
}
dump('areaM2(48.4)', areaM2(48.4).toFixed(9));
dump('velocityMs(2,29.3)', velocityMs(2,29.3).toFixed(6));
dump('maxFlowForVel(29.3,2.5)', maxFlowForVel(29.3,2.5).toFixed(6));

note('=== pressure / PRV engine ===');
var pdata=[];
for(var i=0;i<10;i++) pdata.push({dwellings:i>=1?6:0, pump:0});
var pr=pressurePass({data:pdata, rl:{main:10,pump:12,highest:40,floorToFloor:3.1,
  inletPressure:500,frictionLoss:80,minPressure:250}, flow:3.2, material:'copper_type_b',
  settings:PRESSURE_DEFAULTS});
dump('topServed', pr.topServed);
for(var b=0;b<pr.byLevel.length;b++)
  dump('level '+b+' pressure', (pr.byLevel[b].pressure==null?'-':pr.byLevel[b].pressure.toFixed(3))+
    ' prv='+pr.byLevel[b].needsPrv+' set='+pr.byLevel[b].prvSet);
dump('firstPrvIdx', pr.firstPrvIdx);
dump('prvLevels', pr.prvLevels);
dump('prvDwellings', pr.prvDwellings);
dump('maxPipePressure', pr.maxPipePressure==null?'-':pr.maxPipePressure.toFixed(3));
dump('duty', pr.duty? [pr.duty.Q.toFixed(4),pr.duty.P.toFixed(3),pr.duty.head.toFixed(3),pr.duty.kW].join('/') : '-');
dump('warnings', pr.warnings.map(function(w){return w.text;}).join(' | '));

note('=== a drawn cold-water job ===');
switchService('cw');
var cw=curSvc(); cw.nodes=[]; cw.pipes=[]; state.nextId=1;
cw.network.material='copper_type_b'; cw.network.maxVelocity=2.5;
var src={id:nid(),type:'source',x:160,y:levelY(1)+56,name:'MAINS SUPPLY'};
cw.nodes.push(src);
var made=[];
for(var r=0;r<3;r++){
  var nd={id:nid(),type:'riser',x:420+r*340,name:'CW RISER '+(r+1),start:1,
    data:state.building.levels.map(function(){return blankLevel();}),rl:blankRl()};
  for(var L=1;L<10;L++){ nd.data[L].dwellings=4+r; nd.data[L].lu=(r===2? 12:0); }
  nd.data[9].extra=(r===1?0.35:0);
  cw.nodes.push(nd); made.push(nd);
}
var prevAtt={node:src.id}, prevPt={x:src.x,y:src.y};
for(var k=0;k<made.length;k++){
  var att={node:made[k].id,level:1}, qq=attachPoint(att);
  var pts = prevAtt.level!=null
    ? [{x:prevPt.x,y:prevPt.y},{x:prevPt.x,y:Math.min(prevPt.y,qq.y)},{x:qq.x,y:Math.min(prevPt.y,qq.y)},{x:qq.x,y:qq.y}]
    : [{x:prevPt.x,y:prevPt.y},{x:qq.x,y:prevPt.y},{x:qq.x,y:qq.y}];
  cw.pipes.push({id:nid(),pts:dedupe(pts),a:prevAtt,b:att});
  prevAtt=att; prevPt=qq;
}
var res=sizePipes();
for(var pi=0;pi<cw.pipes.length;pi++){
  var rr=res[cw.pipes[pi].id]||{};
  dump('cw pipe '+pi, (rr.flow==null?'-':rr.flow.toFixed(6))+' DN'+rr.dn+' v='+(rr.vel==null||isNaN(rr.vel)?'-':rr.vel.toFixed(6))+' over='+rr.over+' unsized='+rr.unsized);
}
for(var ri=0;ri<made.length;ri++){
  var nd2=made[ri], inf=riserInfo[nd2.id];
  dump('cw riser '+ri+' base', riserBaseFlow(nd2).toFixed(6)+' feed='+inf.feed);
  var sg=riserSegments(nd2, inf.feed, inf.exports, riserBotIdx(nd2), riserTopIdx(nd2));
  for(var si=0;si<sg.length;si++)
    dump('  seg '+sg[si].i, sg[si].flow.toFixed(6)+' DN'+sg[si].dn+' v='+(isNaN(sg[si].vel)?'-':sg[si].vel.toFixed(6))+' over='+sg[si].over);
  for(var li=0;li<10;li++){ var bb=levelBranch(nd2,li);
    dump('  branch '+li, bb.flow.toFixed(6)+' DN'+bb.dn+' over='+bb.over); }
}

note('=== the hot-water sheet built from it ===');
switchService('hw');
var hw=curSvc();
dump('hw risers', allRisers().length);
var hres=sizePipes();
for(var hp=0;hp<hw.pipes.length;hp++){
  var hr=hres[hw.pipes[hp].id]||{};
  dump('hw pipe '+hp, (hr.flow==null?'-':hr.flow.toFixed(6))+' DN'+hr.dn+' v='+(hr.vel==null||isNaN(hr.vel)?'-':hr.vel.toFixed(6)));
}
var hrs=allRisers();
for(var hi=0;hi<hrs.length;hi++){
  var hinf=riserInfo[hrs[hi].id];
  dump('hw riser '+hi+' base', riserBaseFlow(hrs[hi]).toFixed(6)+' feed='+hinf.feed);
  var hsg=riserSegments(hrs[hi], hinf.feed, hinf.exports, riserBotIdx(hrs[hi]), riserTopIdx(hrs[hi]));
  for(var hsi=0;hsi<hsg.length;hsi++)
    dump('  seg '+hsg[hsi].i, hsg[hsi].flow.toFixed(6)+' DN'+hsg[hsi].dn);
}

note('=== drawing geometry ===');
switchService('cw');
render();
var b=contentBounds();
dump('contentBounds', [b.x0,b.y0,b.x1,b.y1].join(','));
dump('pipe path count', document.querySelectorAll('[data-pipe-id]').length);
dump('node count', document.querySelectorAll('[data-node-id]').length);
dump('svg text', document.getElementById('board').textContent.replace(/\s+/g,' ').trim());
