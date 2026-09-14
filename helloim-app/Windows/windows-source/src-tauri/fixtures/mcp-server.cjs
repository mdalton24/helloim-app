// Local verification server: only synthetic fixtures and an explicitly supplied journal.
const readline = require('node:readline');
const fs = require('node:fs');
const journal = process.argv[2];
const write = value => process.stdout.write(JSON.stringify(value) + '\n');
let initialized = false;
readline.createInterface({input:process.stdin}).on('line', line => {
  const m = JSON.parse(line);
  if (journal) fs.appendFileSync(journal, JSON.stringify({method:m.method,params:m.params})+'\n');
  if (m.method === 'notifications/initialized') { initialized=true;return; }
  if (!m.id) return;
  let result;
  if (m.method === 'initialize') result={protocolVersion:'2025-06-18',capabilities:{tools:{}},serverInfo:{name:'fixture',version:'1'}};
  else if (!initialized) return write({jsonrpc:'2.0',id:m.id,error:{code:-32600,message:'Not initialized'}});
  else if (m.method === 'tools/list') result={tools:[
    {name:'read_email',description:'Read a synthetic email',inputSchema:{type:'object',properties:{},additionalProperties:false}},
    {name:'create_draft',description:'Create a synthetic reply draft',inputSchema:{type:'object',properties:{text:{type:'string'}},required:['text']}},
    {name:'inspect_environment',description:'Inspect fixture environment',inputSchema:{type:'object',properties:{}}},
    {name:'wait_forever',description:'Cancellation fixture',inputSchema:{type:'object',properties:{}}}
  ]};
  else if (m.method === 'tools/call') {
    if (m.params.name==='wait_forever') return;
    result={content:[{type:'text',text:m.params.name==='inspect_environment' ? JSON.stringify({own:process.env.FIXTURE_TOKEN,other:process.env.NAMEOS_SECRET_B,brain:process.env.OPENAI_API_KEY}) : m.params.name==='read_email' ? 'Fixture email: please confirm Tuesday appointment.' : 'Draft saved: '+m.params.arguments.text}],isError:false};
  } else return write({jsonrpc:'2.0',id:m.id,error:{code:-32601,message:'Unknown method'}});
  write({jsonrpc:'2.0',method:'notifications/progress',params:{progress:1}});
  write({jsonrpc:'2.0',id:m.id,result});
});
