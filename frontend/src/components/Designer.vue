<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { VueFlow, useVueFlow, type Node, type Edge } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import api from '../api'
const props=defineProps<{modelValue:any,instances:any[]}>()
const emit=defineEmits(['update:modelValue'])
const selected=ref<any>(null), treeExpanded=ref(true), showCatalog=ref(true), validation=ref<any>(null)
const catalog=ref<any[]>([
 {id:'auth-cookie',name:'Cookie',category:'Session'},
 {id:'auth-spnego',name:'Kerberos',category:'Fédération'},
 {id:'auth-username-password-form',name:'Username Password Form',category:'Identifiants'},
 {id:'auth-otp-form',name:'OTP Form',category:'MFA'},
 {id:'auth-webauthn',name:'WebAuthn Authenticator',category:'MFA'},
 {id:'identity-provider-redirector',name:'Identity Provider Redirector',category:'Fédération'},
 {id:'conditional-user-configured',name:'Condition - User Configured',category:'Condition'}
])
const nodes=computed<Node[]>(()=> (props.modelValue.flow.nodes||[]).map((n:any,i:number)=>({id:n.nodeId,position:n.position||{x:100+i*40,y:80+i*100},data:{label:n.displayName,requirement:n.requirement,type:n.type},type:'default'})))
const edges=computed<Edge[]>(()=>nodes.value.slice(1).map((n,i)=>({id:`e-${i}`,source:nodes.value[i].id,target:n.id,animated:false})))
const {fitView}=useVueFlow()
function updateNodes(list:any[]){const p=structuredClone(props.modelValue);p.flow.nodes=list;emit('update:modelValue',p)}
function addComponent(c:any,type='execution'){
 const list=[...(props.modelValue.flow.nodes||[])];const n={nodeId:crypto.randomUUID(),type,providerId:c.id,displayName:c.name,requirement:'REQUIRED',priority:list.length*10+10,config:{},position:{x:100+(list.length%3)*220,y:80+Math.floor(list.length/3)*130},...(type==='subflow'?{children:[]}: {})};list.push(n);updateNodes(list);selected.value=n
}
function addSubflow(){addComponent({id:'basic-flow',name:'Nouveau sous-flux'},'subflow')}
function removeNode(id:string){updateNodes((props.modelValue.flow.nodes||[]).filter((n:any)=>n.nodeId!==id));selected.value=null}
function changeField(field:string,value:any){const list=structuredClone(props.modelValue.flow.nodes||[]);const n=list.find((x:any)=>x.nodeId===selected.value?.nodeId);if(n){n[field]=value;updateNodes(list);selected.value=n}}
function onNodeClick({node}:any){selected.value=(props.modelValue.flow.nodes||[]).find((n:any)=>n.nodeId===node.id)||null}
function onNodeDragStop({node}:any){const list=structuredClone(props.modelValue.flow.nodes||[]);const n=list.find((x:any)=>x.nodeId===node.id);if(n)n.position=node.position;updateNodes(list)}
async function validate(){const id=props.modelValue.project.id;try{await api.post('/projects',props.modelValue);validation.value=(await api.post(`/projects/${id}/validate`)).data}catch(e:any){validation.value={valid:false,errors:[e.response?.data?.detail||'Erreur de validation']}}}
async function loadCatalog(){const instance=props.instances[0];if(!instance)return;const realm=prompt('Realm cible pour découvrir les providers');if(!realm)return;try{const r=await api.get(`/instances/${instance.id}/realms/${encodeURIComponent(realm)}/catalog`);catalog.value=r.data.providers.map((p:any)=>({id:p.id||p.providerId,name:p.displayName||p.name||p.id,category:p.category||'Keycloak'}))}catch{alert('Découverte indisponible. Catalogue local conservé.')}}
watch(()=>props.modelValue.flow.alias,(v)=>{if(!v)return})
</script>
<template>
 <div class="designer-layout">
  <aside class="catalog panel"><div class="panel-title"><b>Composants</b><button class="tiny" @click="showCatalog=!showCatalog">{{showCatalog?'−':'+'}}</button></div><template v-if="showCatalog"><p class="hint">Ajouter au parcours</p><button v-for="c in catalog" :key="c.id" class="catalog-item" @click="addComponent(c)"><span class="node-icon">◇</span><span><b>{{c.name}}</b><small>{{c.category}}</small></span><span class="plus">+</span></button><button class="catalog-item" @click="addSubflow"><span class="node-icon">▱</span><span><b>Sous-flux</b><small>Conteneur hiérarchique</small></span><span class="plus">+</span></button><button class="ghost full" @click="loadCatalog">Découvrir depuis Keycloak</button></template></aside>
  <section class="canvas-wrap"><div class="canvas-toolbar"><div><b>{{modelValue.flow.alias}}</b><span class="muted"> · {{nodes.length}} éléments</span></div><div><button class="ghost" @click="validate">Valider</button></div></div><VueFlow :nodes="nodes" :edges="edges" fit-view-on-init @node-click="onNodeClick" @node-drag-stop="onNodeDragStop"><Background/><MiniMap/><Controls/></VueFlow><div class="tree-panel"><button class="tree-toggle" @click="treeExpanded=!treeExpanded">⌄　Arborescence du flow ({{nodes.length}})</button><div v-if="treeExpanded" class="tree-list"><div v-for="(n,i) in modelValue.flow.nodes" :key="n.nodeId" class="tree-row" @click="selected=n"><span>{{n.type==='subflow'?'▱':'◇'}}</span>{{i+1}}. {{n.displayName}} <small>{{n.requirement}}</small></div></div></div></section>
  <aside class="properties panel"><b>Propriétés</b><template v-if="selected"><p class="hint">Composant sélectionné</p><label>Nom affiché<input :value="selected.displayName" @input="changeField('displayName',($event.target as HTMLInputElement).value)"></label><label>Requirement<select :value="selected.requirement" @change="changeField('requirement',($event.target as HTMLSelectElement).value)"><option>REQUIRED</option><option>ALTERNATIVE</option><option>CONDITIONAL</option><option>DISABLED</option></select></label><label>Priorité<input type="number" :value="selected.priority" @input="changeField('priority',Number(($event.target as HTMLInputElement).value))"></label><label>Provider ID<input :value="selected.providerId" @input="changeField('providerId',($event.target as HTMLInputElement).value)"></label><button class="danger full" @click="removeNode(selected.nodeId)">Supprimer le composant</button></template><p v-else class="empty">Sélectionnez un composant pour modifier ses propriétés.</p><div v-if="validation" class="validation" :class="validation.valid?'ok':'bad'"><b>{{validation.valid?'Validation réussie':'Erreurs de validation'}}</b><p v-for="e in validation.errors" :key="e">{{e}}</p><p v-for="w in validation.warnings" :key="w">Attention : {{w}}</p></div></aside>
 </div>
</template>
