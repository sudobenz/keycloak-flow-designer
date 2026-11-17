<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, toRaw, watch } from 'vue'
import { VueFlow, Handle, MarkerType, Position, type Node, type Edge } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import api from '../api'
import { flowTemplates } from '../templates'
import { createUuid } from '../utils/id'
const props=defineProps<{modelValue:any,instances:any[],role:string}>()
const emit=defineEmits(['update:modelValue','saved','message','error'])
const selectedId=ref<string|null>(null), treeExpanded=ref(true), showCatalog=ref(true), draggedId=ref<string|null>(null)
const instanceId=ref(props.modelValue.target?.instanceId||''), realm=ref(props.modelValue.target?.realm||''), realms=ref<any[]>([]), flows=ref<any[]>([])
const catalog=ref<any[]>([]), clientCatalog=ref<any[]>([]), formActionProviders=ref<any[]>([]), formProviders=ref<any[]>([]), catalogSource=ref('')
// Catalogue de base utilisable sans connexion à Keycloak. Il permet de construire
// un workflow local avant de sélectionner une instance cible.
const localCatalog=[
 {id:'auth-cookie',displayName:'Cookie — session existante',category:'Session',defaultRequirement:'ALTERNATIVE'},
 {id:'auth-spnego',displayName:'Kerberos / SPNEGO',category:'Authentification',defaultRequirement:'ALTERNATIVE'},
 {id:'auth-username-password-form',displayName:'Formulaire identifiant / mot de passe',category:'Authentification',defaultRequirement:'REQUIRED'},
 {id:'auth-otp-form',displayName:'Formulaire OTP',category:'MFA',defaultRequirement:'REQUIRED'},
 {id:'webauthn-authenticator',displayName:'WebAuthn',category:'MFA',defaultRequirement:'ALTERNATIVE'},
 {id:'webauthn-passwordless-authenticator',displayName:'WebAuthn sans mot de passe',category:'MFA',defaultRequirement:'ALTERNATIVE'},
 {id:'auth-x509-client-username-form',displayName:'Certificat client X.509',category:'Authentification',defaultRequirement:'ALTERNATIVE'},
 {id:'identity-provider-redirector',displayName:'Redirection vers un fournisseur d’identité',category:'Fédération',defaultRequirement:'ALTERNATIVE'},
 {id:'idp-review-profile',displayName:'Vérification du profil fournisseur d’identité',category:'Fédération',defaultRequirement:'REQUIRED'},
 {id:'conditional-user-configured',displayName:'Condition — utilisateur configuré',category:'Conditions',defaultRequirement:'REQUIRED',requirementChoices:['REQUIRED']},
 {id:'conditional-user-role',displayName:'Condition — rôle utilisateur',category:'Conditions',defaultRequirement:'REQUIRED',requirementChoices:['REQUIRED']},
 {id:'conditional-user-attribute',displayName:'Condition — attribut utilisateur',category:'Conditions',defaultRequirement:'REQUIRED',requirementChoices:['REQUIRED']},
 {id:'conditional-client-scope',displayName:'Condition — client scope',category:'Conditions',defaultRequirement:'REQUIRED',requirementChoices:['REQUIRED']},
 {id:'conditional-sub-flow-executed',displayName:'Condition — sous-flux exécuté',category:'Conditions',defaultRequirement:'REQUIRED',requirementChoices:['REQUIRED']},
 {id:'conditional-level-of-authentication',displayName:'Condition — niveau d’authentification (LoA)',category:'Conditions',defaultRequirement:'REQUIRED',requirementChoices:['REQUIRED']},
 {id:'conditional-credential',displayName:'Condition — type de credential',category:'Conditions',defaultRequirement:'REQUIRED',requirementChoices:['REQUIRED']},
 {id:'deny-access-authenticator',displayName:'Refuser l’accès',category:'Contrôle d’accès',defaultRequirement:'REQUIRED',requirementChoices:['REQUIRED']},
 {id:'allow-access-authenticator',displayName:'Autoriser l’accès',category:'Contrôle d’accès',defaultRequirement:'REQUIRED',requirementChoices:['REQUIRED']},
 {id:'auth-recovery-authn-code-form',displayName:'Formulaire de codes de récupération',category:'MFA',defaultRequirement:'ALTERNATIVE'}
]
// FormActionFactory est un SPI distinct des AuthenticatorFactory. Ce catalogue
// embarqué sert de point de départ ; la découverte du Realm reste prioritaire.
const localFormActionCatalog=[
 {id:'registration-user-creation',displayName:'Registration User Creation',category:'Inscription',defaultRequirement:'REQUIRED'},
 {id:'registration-profile-action',displayName:'Registration Profile',category:'Inscription',defaultRequirement:'REQUIRED'},
 {id:'registration-password-action',displayName:'Registration Password',category:'Inscription',defaultRequirement:'REQUIRED'},
 {id:'registration-recaptcha-action',displayName:'Registration reCAPTCHA',category:'Sécurité',defaultRequirement:'DISABLED'},
 {id:'registration-terms-and-conditions',displayName:'Registration Terms and Conditions',category:'Conformité',defaultRequirement:'DISABLED'}
]
const catalogSearch=ref(''), quickProviderId=ref('auth-cookie'), newSubflowType=ref<'basic'|'form'>('basic'), selectedFormProviderId=ref('registration-page-form')
const customProviderOpen=ref(false), customProviderId=ref(''), customProviderName=ref('')
const importAlias=ref(''), deployMode=ref('create'), deployAlias=ref(props.modelValue.flow.alias||''), allowDeletes=ref(false)
const validation=ref<any>(null), deploymentPreview=ref<any>(null), confirmValue=ref(''), deployOpen=ref(false)
const jsonConfig=ref('{}'), propertySchemas=ref<any[]>([]), templateSelection=ref('')
const selected=computed(()=>findNode(props.modelValue.flow.nodes||[],selectedId.value))
const historySnapshots=ref<string[]>([]), historyCursor=ref(-1)
const canUndo=computed(()=>historyCursor.value>0)
const canRedo=computed(()=>historyCursor.value>=0&&historyCursor.value<historySnapshots.value.length-1)
let historyApplying=false, lastHistorySnapshot='', historyTimer:ReturnType<typeof setTimeout>|null=null
const canDeploy=computed(()=>props.role==='admin' && !!instanceId.value && !!realm.value)
const flowBindingFields=[
 {key:'browserFlow',label:'Authentification navigateur'},
 {key:'registrationFlow',label:'Inscription'},
 {key:'directGrantFlow',label:'Direct Grant'},
 {key:'resetCredentialsFlow',label:'Réinitialisation des identifiants'},
 {key:'clientAuthenticationFlow',label:'Authentification des clients'},
 {key:'dockerAuthenticationFlow',label:'Authentification Docker'},
 {key:'firstBrokerLoginFlow',label:'Première connexion via IdP'}
]
const flowBindings=ref<any>({})
const bindingsSaving=ref(false)
let flowInstance:any=null
function onFlowInit(instance:any){flowInstance=instance;instance.fitView?.({padding:0.18})}
function findNode(nodes:any[],id:string|null):any{if(!id)return null;for(const n of nodes||[]){if(n.nodeId===id)return n;const c=findNode(n.children||[],id);if(c)return c}return null}
// Les props Vue sont des Proxy réactifs. structuredClone() ne sait pas cloner
// directement un Proxy et levait DataCloneError au premier clic sur « Ajouter ».
// On retire récursivement les Proxy Vue avant de cloner le modèle JSON.
function unwrapVueProxy(value:any):any{
 const raw=toRaw(value)
 if(Array.isArray(raw))return raw.map((item:any)=>unwrapVueProxy(item))
 if(raw&&typeof raw==='object'){
  const result:any={}
  for(const [key,item] of Object.entries(raw))result[key]=unwrapVueProxy(item)
  return result
 }
 return raw
}
function clone(){return structuredClone(unwrapVueProxy(props.modelValue))}
function applyTemplate(id:string){const template=flowTemplates.find(x=>x.id===id);templateSelection.value='';if(!template)return;if((props.modelValue.flow.nodes||[]).length&&!confirm('Remplacer le contenu actuel par ce modèle ?'))return;const p=clone();p.project={...p.project,name:template.label,description:template.description};p.flow=structuredClone(template.flow);p.target={};emitProject(p);selectedId.value=null;deployAlias.value=p.flow.alias;validation.value=null;emit('message',`Modèle « ${template.label} » chargé. Vérifier les providers avant le déploiement.`)}
function emitProject(next:any){emit('update:modelValue',next)}
function serializeProject(){return JSON.stringify(unwrapVueProxy(props.modelValue))}
function commitHistory(){
 const snapshot=serializeProject()
 if(snapshot===lastHistorySnapshot)return
 const kept=historySnapshots.value.slice(0,historyCursor.value+1)
 kept.push(snapshot)
 historySnapshots.value=kept
 historyCursor.value=kept.length-1
 lastHistorySnapshot=snapshot
}
function scheduleHistory(){
 if(historyApplying)return
 if(historyTimer)clearTimeout(historyTimer)
 historyTimer=setTimeout(()=>{historyTimer=null;commitHistory()},180)
}
function flushHistory(){if(historyTimer){clearTimeout(historyTimer);historyTimer=null}commitHistory()}
function restoreHistory(index:number){
 flushHistory()
 if(index<0||index>=historySnapshots.value.length||index===historyCursor.value)return
 historyCursor.value=index
 const snapshot=historySnapshots.value[index]
 historyApplying=true
 lastHistorySnapshot=snapshot
 emitProject(JSON.parse(snapshot))
 selectedId.value=null
 nextTick(()=>{historyApplying=false;lastHistorySnapshot=serializeProject()})
}
function undo(){if(canUndo.value)restoreHistory(historyCursor.value-1)}
function redo(){if(canRedo.value)restoreHistory(historyCursor.value+1)}
function locateNode(nodes:any[],id:string|null,parent:any=null):any{
 if(!id)return null
 for(let index=0;index<(nodes||[]).length;index++){
  const node=nodes[index]
  if(node.nodeId===id)return {list:nodes,index,node,parent}
  if(node.type==='subflow'){
   const found=locateNode(node.children||[],id,node)
   if(found)return found
  }
 }
 return null
}
function flowProviderForContainer(container:any):string{
 if(!container)return props.modelValue.flow.providerId||'basic-flow'
 return ['form','form-flow'].includes(container.flowType)?'form-flow':container.flowType==='client-flow'?'client-flow':'basic-flow'
}
function executionKindForFlowProvider(flowProvider:string):string{
 return flowProvider==='form-flow'?'form-action':flowProvider==='client-flow'?'client-authenticator':'authenticator'
}
const activeInsertionContext=computed(()=>{
 const location=locateNode(props.modelValue.flow.nodes||[],selectedId.value)
 const container=location?.node?.type==='subflow'?location.node:(location?.parent||null)
 const parentFlowProvider=flowProviderForContainer(container)
 return {container,parentFlowProvider,executionKind:executionKindForFlowProvider(parentFlowProvider),label:container?.displayName||'Flow principal'}
})
const selectedContext=computed(()=>activeInsertionContext.value.label)
function subflowRequirementChoices(flowType:string){return ['form','form-flow'].includes(flowType)?['REQUIRED','DISABLED']:['REQUIRED','ALTERNATIVE','CONDITIONAL','DISABLED']}
function walk(nodes:any[],depth=0,parent='root',rows:any[]=[]){for(const n of nodes||[]){rows.push({...n,depth,parent});if(n.type==='subflow')walk(n.children||[],depth+1,n.nodeId,rows)}return rows}
const treeRows=computed(()=>walk(props.modelValue.flow.nodes||[]))
const layoutAxis=ref<'TB'|'LR'>('TB')
const graph=computed(()=>{
 const graphNodes:Node[]=[]
 const graphEdges:Edge[]=[]
 const vertical=layoutAxis.value==='TB'
 const rootX=vertical?95:70
 const rootY=vertical?70:95
 const depthGap=vertical?300:250
 const stepGap=vertical?185:285
 const sequence=(items:any[],depth:number,startCursor:number):{firstId:string|null,lastId:string|null,nextCursor:number}=>{
  let cursor=startCursor
  let firstId:string|null=null
  let previousTerminal:string|null=null
  let previousEndedInSubflow=false
  for(let index=0;index<items.length;index++){
   const item=items[index]
   const id=String(item.nodeId)
   if(!firstId)firstId=id
   const step=Number(item.priority)||((index+1)*10)
   graphNodes.push({
    id,type:'default',position:vertical?{x:rootX+depth*depthGap,y:cursor}:{x:cursor,y:rootY+depth*depthGap},draggable:false,selectable:true,
    data:{nodeId:id,label:item.displayName||item.providerId||'Composant',detail:item.type==='subflow'?`${item.flowType==='form'?'Sous-flow Form':'Sous-flow Basic'} · ${item.children?.length||0} enfant(s)`:`${item.providerId||'Provider'} · ${item.executionKind==='form-action'?'Form Action':item.executionKind==='client-authenticator'?'Client Authenticator':'Authenticator'}`,type:item.type,requirement:item.requirement||'REQUIRED',step:index+1,priority:step,isSubflow:item.type==='subflow',flowType:item.flowType},
    class:[item.type==='subflow'?'subflow-node':'execution-node',`${String(item.requirement||'REQUIRED').toLowerCase()}-node`]
   })
   if(previousTerminal){
    graphEdges.push({id:`edge-${previousTerminal}-${id}`,source:previousTerminal,target:id,type:'smoothstep',animated:false,markerEnd:{type:MarkerType.ArrowClosed,color:previousEndedInSubflow?'#8b5cf6':'#5794ed'},label:previousEndedInSubflow?`retour parent · priorité ${step}`:`priorité ${step}`,style:previousEndedInSubflow?{stroke:'#8b5cf6',strokeWidth:2,strokeDasharray:'5 4'}:{stroke:'#5794ed',strokeWidth:2}})
   }
   let terminal=id
   let nextCursor=cursor+stepGap
   let endedInSubflow=false
   if(item.type==='subflow'&&(item.children||[]).length){
    const children=sequence(item.children||[],depth+1,cursor+(vertical?150:220))
    if(children.firstId){
     graphEdges.push({id:`enter-${id}-${children.firstId}`,source:id,target:children.firstId,type:'smoothstep',animated:false,markerEnd:{type:MarkerType.ArrowClosed,color:'#8b5cf6'},label:'entrée sous-flow',style:{stroke:'#8b5cf6',strokeWidth:2}})
     terminal=children.lastId||id
     nextCursor=Math.max(nextCursor,children.nextCursor+(vertical?42:50))
     endedInSubflow=true
    }
   }
   previousTerminal=terminal
   previousEndedInSubflow=endedInSubflow
   cursor=nextCursor
  }
  return {firstId,lastId:previousTerminal,nextCursor:cursor}
 }
 const root=sequence(props.modelValue.flow.nodes||[],0,rootY)
 if(root.firstId){
  graphNodes.unshift({id:'__flow_start__',type:'default',position:vertical?{x:rootX,y:0}:{x:0,y:rootY},draggable:false,selectable:false,data:{kind:'start',label:'DÉBUT DU FLOW'}} as Node)
  graphNodes.push({id:'__flow_end__',type:'default',position:vertical?{x:rootX,y:root.nextCursor+12}:{x:root.nextCursor+12,y:rootY},draggable:false,selectable:false,data:{kind:'end',label:'FIN DU FLOW'}} as Node)
  graphEdges.push({id:'edge-flow-start',source:'__flow_start__',target:root.firstId,type:'smoothstep',markerEnd:{type:MarkerType.ArrowClosed,color:'#16a34a'},style:{stroke:'#16a34a',strokeWidth:2},label:'début'})
  if(root.lastId)graphEdges.push({id:`edge-${root.lastId}-flow-end`,source:root.lastId,target:'__flow_end__',type:'smoothstep',markerEnd:{type:MarkerType.ArrowClosed,color:'#dc6470'},style:{stroke:'#dc6470',strokeWidth:2},label:'fin'})
 }
 return {nodes:graphNodes,edges:graphEdges}
})
const nodes=computed<Node[]>(()=>graph.value.nodes)
const edges=computed<Edge[]>(()=>graph.value.edges)
const catalogEntries=computed(()=>{
 const merged=new Map<string,any>()
 // Lorsque la connexion est active, le catalogue serveur est la source de vérité.
 // Le catalogue embarqué n'est utilisé qu'en mode hors ligne / sans découverte.
 if(catalogSource.value!=='keycloak')for(const provider of localCatalog)merged.set(provider.id,{...provider})
 for(const provider of catalog.value){
  const id=String(provider.id||provider.providerId||'').trim()
  if(!id)continue
  const previous=merged.get(id)||{}
  merged.set(id,{...previous,...provider,id,displayName:provider.displayName||provider.name||previous.displayName||id})
 }
 return [...merged.values()].sort((a,b)=>String(a.displayName).localeCompare(String(b.displayName),'fr'))
})
const filteredCatalog=computed(()=>{
 const q=catalogSearch.value.trim().toLocaleLowerCase('fr')
 return q?activeCatalogEntries.value.filter((p:any)=>`${p.displayName} ${p.id} ${p.category||''}`.toLocaleLowerCase('fr').includes(q)):activeCatalogEntries.value
})
const clientCatalogEntries=computed(()=>clientCatalog.value.map((provider:any)=>{
 const id=String(provider.id||provider.providerId||provider.alias||'').trim()
 return {...provider,id,displayName:provider.displayName||provider.name||id,executionKind:'client-authenticator',category:provider.category||'Authentification client',requirementChoices:provider.requirementChoices||['ALTERNATIVE','REQUIRED','DISABLED']}
 }).filter((provider:any)=>provider.id))
const formProviderCatalogEntries=computed(()=>{
 const local=[{id:'registration-page-form',displayName:'Page d’inscription Keycloak',description:'FormAuthenticator standard de Keycloak'}]
 const source=catalogSource.value==='keycloak'?formProviders.value:local
 return source.map((provider:any)=>{const id=String(provider.id||provider.providerId||'').trim();return {...provider,id,displayName:provider.displayName||provider.name||id}}).filter((provider:any)=>provider.id)
})
const formActionCatalogEntries=computed(()=>{
 const merged=new Map<string,any>()
 if(catalogSource.value!=='keycloak')for(const provider of localFormActionCatalog)merged.set(provider.id,{...provider,executionKind:'form-action',requirementChoices:['REQUIRED','DISABLED']})
 for(const provider of formActionProviders.value){
  const id=String(provider.id||provider.providerId||'').trim()
  if(!id)continue
  const previous=merged.get(id)||{}
  merged.set(id,{...previous,...provider,id,displayName:provider.displayName||provider.name||previous.displayName||id,executionKind:'form-action',requirementChoices:['REQUIRED','DISABLED']})
 }
 return [...merged.values()].sort((a,b)=>String(a.displayName).localeCompare(String(b.displayName),'fr'))
})
const activeCatalogEntries=computed(()=>activeInsertionContext.value.executionKind==='form-action'?formActionCatalogEntries.value:activeInsertionContext.value.executionKind==='client-authenticator'?clientCatalogEntries.value:catalogEntries.value)
const quickCatalogEntries=computed(()=>activeCatalogEntries.value)
const filteredClientCatalog=computed(()=>{
 const q=catalogSearch.value.trim().toLocaleLowerCase('fr')
 return q?clientCatalogEntries.value.filter((p:any)=>`${p.displayName} ${p.id}`.toLocaleLowerCase('fr').includes(q)):clientCatalogEntries.value
})
const filteredFormActionCatalog=computed(()=>filteredCatalog.value)
const quickProviderLabel=computed(()=>quickCatalogEntries.value.find((p:any)=>p.id===quickProviderId.value)?.displayName||'un composant')
const directionLabel=computed(()=>layoutAxis.value==='TB'?'haut → bas':'gauche → droite')
const requirementChoices=computed(()=>{
 if(selected.value?.requirementChoices?.length)return selected.value.requirementChoices
 if(selected.value?.type==='subflow')return subflowRequirementChoices(selected.value.flowType||'basic')
 if(selected.value?.executionKind==='form-action')return ['REQUIRED','DISABLED']
 if(selected.value?.executionKind==='client-authenticator')return ['ALTERNATIVE','REQUIRED','DISABLED']
 return ['REQUIRED','ALTERNATIVE','DISABLED']
})
function updateFlow(key:string,value:any){const p=clone();p.flow[key]=value;emitProject(p)}
function updateNode(id:string,mutator:(n:any)=>void){const p=clone();function visit(nodes:any[]):boolean{for(const n of nodes){if(n.nodeId===id){mutator(n);return true}if(visit(n.children||[]))return true}return false}visit(p.flow.nodes);emitProject(p)}
function getParentFlowProviderForNode(id:string):string{
 const location=locateNode(props.modelValue.flow.nodes||[],id)
 return flowProviderForContainer(location?.parent||null)
}
function changeProviderId(id:string,value:string){const providerId=value.trim();if(!providerId)return;const parentProvider=getParentFlowProviderForNode(id);updateNode(id,n=>{n.providerId=providerId;n.executionKind=executionKindForFlowProvider(parentProvider);n.requirementChoices=parentProvider==='form-flow'?['REQUIRED','DISABLED']:parentProvider==='client-flow'?['ALTERNATIVE','REQUIRED','DISABLED']:['REQUIRED','ALTERNATIVE','DISABLED'];if(!n.requirementChoices.includes(n.requirement))n.requirement='REQUIRED';n.config={};n.remoteConfigId=null;n.configReadWarning=null});propertySchemas.value=[];jsonConfig.value='{}';nextTick(()=>loadConfigSchema())}
function chooseNode(id:string){selectedId.value=id;if(findNode(props.modelValue.flow.nodes,id)?.config)jsonConfig.value=JSON.stringify(findNode(props.modelValue.flow.nodes,id).config,null,2);loadConfigSchema()}
function addNode(provider:any,type='execution',requestedSubflowType:'basic'|'form'='basic'){
 const p=clone()
 const selectedLocation=locateNode(p.flow.nodes,selectedId.value)
 let target=p.flow.nodes
 let insertIndex=target.length
 let targetLabel='Flow principal'
 let targetContainer:any=null
 if(selectedLocation?.node?.type==='subflow'){
  targetContainer=selectedLocation.node
  target=selectedLocation.node.children||(selectedLocation.node.children=[])
  insertIndex=target.length
  targetLabel=selectedLocation.node.displayName||selectedLocation.node.alias||'Sous-flow'
 }else if(selectedLocation){
  targetContainer=selectedLocation.parent||null
  target=selectedLocation.list
  insertIndex=selectedLocation.index+1
  targetLabel=selectedLocation.parent?.displayName||'Flow principal'
 }
 const parentProvider=targetContainer?(targetContainer.flowType==='form'?'form-flow':'basic-flow'):(p.flow.providerId||'basic-flow')
 if(type==='subflow'&&parentProvider==='form-flow'){
  emit('error','Un Form flow contient des Form Action providers. Il ne peut pas accueillir un sous-flow imbriqué.')
  return
 }
 if(type==='subflow'&&parentProvider==='client-flow'&&requestedSubflowType==='form'){
  emit('error','Un Form flow ne peut pas être ajouté dans un flow d’authentification client.')
  return
 }
 const flowType=type==='subflow'?requestedSubflowType:undefined
 const executionKind=type==='execution'?executionKindForFlowProvider(parentProvider):undefined
 const choices=type==='subflow'?subflowRequirementChoices(flowType!):provider.requirementChoices?.length?provider.requirementChoices:(executionKind==='form-action'?['REQUIRED','DISABLED']:executionKind==='client-authenticator'?['ALTERNATIVE','REQUIRED','DISABLED']:['REQUIRED','ALTERNATIVE','DISABLED'])
 const n:any={nodeId:createUuid(),type,displayName:provider.displayName||provider.name||provider.id,providerId:provider.id,executionKind,configurable:provider.configurable,description:provider.description||'',requirement:provider.defaultRequirement||'REQUIRED',requirementChoices:choices,priority:10,config:{},configAlias:'',position:{x:80,y:80},...(type==='subflow'?{alias:'',description:'',flowType,formProviderId:flowType==='form'?(selectedFormProviderId.value||'registration-page-form'):null,children:[]}: {})}
 if(!choices.includes(n.requirement))n.requirement=choices[0]||'REQUIRED'
 target.splice(insertIndex,0,n)
 const normalize=(list:any[])=>list.forEach((node:any,index:number)=>{node.priority=(index+1)*10;normalize(node.children||[])})
 normalize(p.flow.nodes)
 emitProject(p)
 selectedId.value=n.nodeId
 jsonConfig.value='{}'
 propertySchemas.value=[]
 loadConfigSchema()
 emit('message',`${n.displayName} ajouté dans « ${targetLabel} » à la position ${insertIndex+1}.`)
}
function addSubflow(flowType:'basic'|'form'=newSubflowType.value){addNode({id:'basic-flow',displayName:flowType==='form'?'Nouveau sous-flow Form':'Nouveau sous-flow Basic'},'subflow',flowType)}
function duplicateNodeSelected(){
 if(!selectedId.value)return
 const p=clone(),location=locateNode(p.flow.nodes,selectedId.value)
 if(!location)return
 const makeCopy=(source:any):any=>{
  const copy=structuredClone(source)
  const renew=(node:any)=>{
   node.nodeId=createUuid()
   delete node.remoteExecutionId;delete node.remoteFlowId;delete node.remoteAlias;delete node.remoteConfigId;delete node.remote;delete node.configReadWarning
   if(node.type==='subflow')node.alias=''
   if(node.configAlias)node.configAlias=`${node.configAlias} copie`
   node.children=(node.children||[]).map((child:any)=>{const cloned=structuredClone(child);renew(cloned);return cloned})
  }
  renew(copy)
  copy.displayName=`${copy.displayName||'Composant'} (copie)`
  return copy
 }
 const copy=makeCopy(location.node)
 location.list.splice(location.index+1,0,copy)
 const normalize=(list:any[])=>list.forEach((node:any,index:number)=>{node.priority=(index+1)*10;normalize(node.children||[])})
 normalize(p.flow.nodes)
 emitProject(p);selectedId.value=copy.nodeId
 emit('message',`« ${copy.displayName} » dupliqué. Les identifiants Keycloak seront créés au déploiement.`)
}
function addQuickProvider(){
 const available=quickCatalogEntries.value
 const provider=available.find((item:any)=>item.id===quickProviderId.value)||available[0]
 if(provider)addNode(provider)
 else emit('error',activeInsertionContext.value.executionKind==='form-action'?'Aucune Form Action découverte. Connectez une instance Keycloak ou ajoutez un Provider ID personnalisé.':activeInsertionContext.value.executionKind==='client-authenticator'?'Aucun Client Authenticator découvert. Connectez une instance ou ajoutez un Provider ID personnalisé.':'Aucun authenticator disponible.')
}
function createCustomProvider(){
 const id=customProviderId.value.trim()
 const displayName=customProviderName.value.trim()||id
 if(!id){emit('error','Le Provider ID est obligatoire.');return}
 if(!/^[A-Za-z0-9._:-]+$/.test(id)){emit('error','Le Provider ID contient des caractères non autorisés.');return}
 const kind=activeInsertionContext.value.executionKind
 const choices=kind==='form-action'?['REQUIRED','DISABLED']:kind==='client-authenticator'?['ALTERNATIVE','REQUIRED','DISABLED']:['REQUIRED','ALTERNATIVE','DISABLED']
 addNode({id,displayName,executionKind:kind,requirementChoices:choices})
 customProviderOpen.value=false
 customProviderId.value=''
 customProviderName.value=''
 emit('message',`Composant personnalisé « ${displayName} » ajouté. Vérifier que le Provider ID existe dans le SPI ${kind} de la version Keycloak cible.`)
}
function containsNodeId(node:any,id:string|null):boolean{return !!id&&!!node&&(node.nodeId===id||(node.children||[]).some((child:any)=>containsNodeId(child,id)))}
function deleteNode(id:string){
 const p=clone()
 const location=locateNode(p.flow.nodes,id)
 if(!location)return
 const removed=location.list.splice(location.index,1)[0]
 const normalize=(list:any[])=>list.forEach((node:any,index:number)=>{node.priority=(index+1)*10;normalize(node.children||[])})
 normalize(p.flow.nodes)
 emitProject(p)
 if(selectedId.value===id||containsNodeId(removed,selectedId.value))selectedId.value=null
 propertySchemas.value=[]
 jsonConfig.value='{}'
 emit('message',`« ${removed?.displayName||'Élément'} » supprimé du projet local. Annulation possible avec Ctrl+Z. La suppression distante sera appliquée au déploiement uniquement si elle est explicitement autorisée.`)
}
function changeFormProvider(id:string,providerId:string){
 const current=findNode(props.modelValue.flow.nodes||[],id)
 if(!current||current.remoteExecutionId){emit('error','Le FormAuthenticator d’un sous-flow déjà déployé ne peut pas être changé en place.');return}
 updateNode(id,node=>node.formProviderId=providerId)
}
function changeSubflowType(id:string,flowType:string){
 const existing=findNode(props.modelValue.flow.nodes||[],id)
 const wantedKind=flowType==='form'?'form-action':'authenticator'
 const incompatible=(existing?.children||[]).some((child:any)=>child.type==='subflow'||(child.executionKind&&child.executionKind!==wantedKind))
 if(incompatible){emit('error',`Impossible de changer ce sous-flow en ${flowType==='form'?'Form':'Basic'} : son contenu contient des composants incompatibles. Supprimez ou recréez les exécutions concernées.`);return}
 updateNode(id,(node)=>{
  node.flowType=flowType
  node.requirementChoices=subflowRequirementChoices(flowType)
  if(!node.requirementChoices.includes(node.requirement))node.requirement='REQUIRED'
  for(const child of node.children||[]){child.executionKind=wantedKind;child.requirementChoices=flowType==='form'?['REQUIRED','DISABLED']:['REQUIRED','ALTERNATIVE','DISABLED']}
 })
}
function reorder(delta:number){if(!selected.value)return;const p=clone();function visit(nodes:any[]):boolean{const i=nodes.findIndex(n=>n.nodeId===selectedId.value);if(i>=0){const j=i+delta;if(j<0||j>=nodes.length)return true;[nodes[i],nodes[j]]=[nodes[j],nodes[i]];nodes.forEach((n,k)=>n.priority=(k+1)*10);return true}return nodes.some(n=>visit(n.children||[]))}visit(p.flow.nodes);emitProject(p)}
function dropTree(targetId:string){
 const sourceId=draggedId.value
 draggedId.value=null
 if(!sourceId||sourceId===targetId)return
 const p=clone()
 const contains=(node:any,id:string):boolean=>(node.children||[]).some((child:any)=>child.nodeId===id||contains(child,id))
 const source=findNode(p.flow.nodes,sourceId)
 const target=findNode(p.flow.nodes,targetId)
 if(!source||!target||contains(source,targetId))return
 const targetLocation=locateNode(p.flow.nodes,targetId)
 const sourceLocation=locateNode(p.flow.nodes,sourceId)
 const destinationContainer=target.type==='subflow'?target:(targetLocation?.parent||null)
 const destinationProvider=destinationContainer?(destinationContainer.flowType==='form'?'form-flow':'basic-flow'):(p.flow.providerId||'basic-flow')
 const sourceProvider=sourceLocation?.parent?(sourceLocation.parent.flowType==='form'?'form-flow':'basic-flow'):(p.flow.providerId||'basic-flow')
 if(destinationProvider==='form-flow'&&source.type==='subflow'){
  emit('error','Un Form flow ne peut pas contenir de sous-flow imbriqué.');return
 }
 if(destinationProvider==='client-flow'&&source.type==='subflow'&&source.flowType==='form'){
  emit('error','Un sous-flow Form ne peut pas être déplacé dans un flow d’authentification client.');return
 }
 if(source.type==='execution'){
  const expectedKind=executionKindForFlowProvider(destinationProvider)
  const actualKind=source.executionKind||executionKindForFlowProvider(sourceProvider)
  if(actualKind!==expectedKind){emit('error',`Déplacement refusé : ce composant est de type ${actualKind}, alors que la destination attend ${expectedKind}.`);return}
 }
 function findList(nodes:any[],id:string):any[]|null{
  if(nodes.some((n:any)=>n.nodeId===id))return nodes
  for(const n of nodes){const found=findList(n.children||[],id);if(found)return found}
  return null
 }
 const sourceList=findList(p.flow.nodes,sourceId)
 const targetList=target.type==='subflow'?(target.children||(target.children=[])):findList(p.flow.nodes,targetId)
 if(!sourceList||!targetList)return
 const from=sourceList.findIndex((n:any)=>n.nodeId===sourceId)
 if(from<0)return
 const [moved]=sourceList.splice(from,1)
 if(target.type==='subflow')targetList.push(moved)
 else {
  const targetIndex=targetList.findIndex((n:any)=>n.nodeId===targetId)
  targetList.splice(targetIndex,0,moved)
 }
 const normalize=(list:any[])=>list.forEach((node:any,index:number)=>{node.priority=(index+1)*10;normalize(node.children||[])})
 normalize(p.flow.nodes)
 emitProject(p)
 emit('message',target.type==='subflow'?'Composant déplacé dans le sous-flux.':'Ordre du workflow mis à jour.')
}
function onNodeClick({node}:any){if(node?.data?.nodeId)chooseNode(node.data.nodeId)}
async function loadRealms(preferred=''){if(!instanceId.value)return;try{realms.value=(await api.get(`/instances/${instanceId.value}/realms`)).data;realm.value=realms.value.some((r:any)=>r.realm===preferred)?preferred:(realms.value[0]?.realm||'')}catch(e:any){emit('error',e.response?.data?.detail||'Lecture des Realms impossible.')}}
async function loadFlowBindings(){
 if(!instanceId.value||!realm.value){flowBindings.value={};return}
 try{flowBindings.value=(await api.get(`/instances/${instanceId.value}/realms/${encodeURIComponent(realm.value)}/flow-bindings`)).data||{}}
 catch(e:any){flowBindings.value={};emit('error',e.response?.data?.detail||'Lecture des bindings de Realm impossible.')}
}
async function saveFlowBindings(){
 if(props.role!=='admin'){emit('error','Le rôle administrateur est requis pour modifier les bindings du Realm.');return}
 bindingsSaving.value=true
 try{
  const response=await api.put(`/instances/${instanceId.value}/realms/${encodeURIComponent(realm.value)}/flow-bindings`,flowBindings.value)
  flowBindings.value=response.data||flowBindings.value
  emit('message','Bindings de flows du Realm mis à jour.')
 }catch(e:any){emit('error',e.response?.data?.detail||'Mise à jour des bindings impossible.')}
 finally{bindingsSaving.value=false}
}
async function loadRemoteData(){if(!instanceId.value||!realm.value)return;try{const [f,c]=await Promise.all([api.get(`/instances/${instanceId.value}/realms/${encodeURIComponent(realm.value)}/flows`),api.get(`/instances/${instanceId.value}/realms/${encodeURIComponent(realm.value)}/catalog`)]);flows.value=f.data;catalog.value=(c.data.providers||[]).map((p:any)=>({...p,id:p.id||p.providerId,displayName:p.displayName||p.name||p.id,executionKind:'authenticator'}));clientCatalog.value=c.data.clientAuthenticatorProviders||[];formActionProviders.value=c.data.formActionProviders||[];formProviders.value=c.data.formProviders||[];if(formProviders.value.length){const available=formProviders.value.map((p:any)=>String(p.id||p.providerId||'')).filter(Boolean);if(!available.includes(selectedFormProviderId.value))selectedFormProviderId.value=available[0]}catalogSource.value=c.data.source}catch(e:any){emit('error',e.response?.data?.detail||'Découverte Keycloak impossible.')}}
watch(()=>JSON.stringify(unwrapVueProxy(props.modelValue)),(snapshot)=>{
 if(!historySnapshots.value.length){historySnapshots.value=[snapshot];historyCursor.value=0;lastHistorySnapshot=snapshot;return}
 if(historyApplying){lastHistorySnapshot=snapshot;return}
 if(snapshot!==lastHistorySnapshot)scheduleHistory()
},{immediate:true,flush:'post'})
watch(nodes,async()=>{await nextTick();flowInstance?.fitView?.({padding:0.18,duration:220})},{flush:'post'})
watch(instanceId,async(next)=>{realms.value=[];flows.value=[];catalog.value=[];clientCatalog.value=[];formActionProviders.value=[];formProviders.value=[];catalogSource.value='';flowBindings.value={};const preferred=props.modelValue.target?.instanceId===next?(props.modelValue.target?.realm||''):'';realm.value='';if(next)await loadRealms(preferred)},{immediate:true})
watch(realm,async()=>{await loadRemoteData();await loadFlowBindings()})
watch(()=>props.modelValue.project?.id,()=>{selectedId.value=null;deployAlias.value=props.modelValue.flow.alias||'';const nextInstance=props.modelValue.target?.instanceId||'';const nextRealm=props.modelValue.target?.realm||'';if(nextInstance!==instanceId.value)instanceId.value=nextInstance;else if(nextRealm!==realm.value)realm.value=nextRealm})
watch(()=>selected.value?.config,(cfg)=>{jsonConfig.value=JSON.stringify(cfg||{},null,2)},{deep:true})
async function importSelected(){if(!importAlias.value)return;try{const p=(await api.get(`/instances/${instanceId.value}/realms/${encodeURIComponent(realm.value)}/flows/${encodeURIComponent(importAlias.value)}/import`)).data;emitProject(p);selectedId.value=null;deployAlias.value=p.flow.alias;emit('message',`Flow « ${p.flow.alias} » importé dans le projet.`)}catch(e:any){emit('error',e.response?.data?.detail||'Import du flow impossible.')}}
async function duplicateSelected(){if(!importAlias.value)return;const newAlias=prompt('Alias du nouveau flow personnalisé');if(!newAlias)return;try{const p=(await api.post(`/instances/${instanceId.value}/realms/${encodeURIComponent(realm.value)}/flows/${encodeURIComponent(importAlias.value)}/duplicate`,{newAlias})).data;emitProject(p);deployAlias.value=newAlias;emit('message',`Flow dupliqué sous « ${newAlias} ».`);await loadRemoteData()}catch(e:any){emit('error',e.response?.data?.detail||'Duplication impossible.')}}
function errorDetail(error:any, fallback:string){
 return error?.response?.data?.detail || error?.message || fallback
}

// Persiste le modèle et retourne toujours l'objet réellement enregistré par l'API.
// Les opérations qui dépendent d'un projet enregistré utilisent cet objet et son ID,
// plutôt que de relire immédiatement la prop v-model (mise à jour asynchrone).
async function persistProject(){
 const payload=clone()
 payload.target={...(payload.target||{}),...(instanceId.value?{instanceId:instanceId.value}:{}),...(realm.value?{realm:realm.value}:{})}
 const response=await api.post('/projects',payload)
 const saved=response.data
 if(!saved?.project?.id)throw new Error('Le serveur n’a pas retourné d’identifiant de projet après l’enregistrement.')
 emitProject(saved)
 emit('saved',saved)
 return saved
}

async function save(){
 try{await persistProject()}
 catch(e:any){emit('error',errorDetail(e,'Sauvegarde impossible.'))}
}

async function validate(){
 try{
  const saved=await persistProject()
  const id=encodeURIComponent(saved.project.id)
  validation.value=(await api.post(`/projects/${id}/validate`)).data
 }catch(e:any){emit('error',errorDetail(e,'Validation impossible.'))}
}

async function openDeploy(){
 if(!canDeploy.value){emit('error','Le déploiement exige un rôle administrateur et une instance/Realm sélectionnés.');return}
 try{
  const saved=await persistProject()
  const id=encodeURIComponent(saved.project.id)
  const response=await api.post(`/projects/${id}/deploy/preview`,{instanceId:instanceId.value,realm:realm.value,mode:deployMode.value,alias:deployAlias.value,allowDeletes:allowDeletes.value,confirmation:deployAlias.value})
  deploymentPreview.value=response.data
  confirmValue.value=''
  deployOpen.value=true
 }catch(e:any){emit('error',errorDetail(e,'Prévisualisation impossible.'))}
}

async function confirmDeploy(){
 try{
  const id=encodeURIComponent(props.modelValue.project.id)
  const result=(await api.post(`/projects/${id}/deploy`,{instanceId:instanceId.value,realm:realm.value,mode:deployMode.value,alias:deployAlias.value,allowDeletes:allowDeletes.value,confirmation:confirmValue.value})).data
  deployOpen.value=false
  if(result.updatedProject){emitProject(result.updatedProject);await api.post('/projects',result.updatedProject)}
  emit('message',result.message||'Déploiement terminé.')
  await loadRemoteData()
 }catch(e:any){emit('error',errorDetail(e,'Déploiement échoué.'))}
}

async function exportProject(){
 try{
  const saved=await persistProject()
  const response=await api.get(`/projects/${encodeURIComponent(saved.project.id)}/export.json`,{responseType:'blob'})
  downloadBlob(response.data,`${saved.project.name||'flow'}.json`,'application/json')
 }catch(e:any){emit('error',errorDetail(e,'Export JSON impossible.'))}
}

async function exportYaml(){
 try{
  const saved=await persistProject()
  const response=await api.get(`/projects/${encodeURIComponent(saved.project.id)}/export.yaml`,{responseType:'blob'})
  downloadBlob(response.data,`${saved.project.name||'flow'}.yaml`,'application/yaml')
 }catch(e:any){emit('error',errorDetail(e,'Export YAML impossible.'))}
}
async function importFile(event:any){const file=event.target.files?.[0];if(!file)return;const form=new FormData();form.append('file',file);try{const p=(await api.post('/projects/import',form,{headers:{'Content-Type':'multipart/form-data'}})).data;emitProject(p);emit('message','Projet JSON importé.')}catch(e:any){emit('error',e.response?.data?.detail||'Import JSON impossible.')}event.target.value=''}
function downloadBlob(blob:Blob,name:string,type:string){const url=URL.createObjectURL(new Blob([blob],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
async function loadConfigSchema(){if(selected.value?.type!=='execution'||!selected.value?.providerId||!instanceId.value||!realm.value){propertySchemas.value=[];return}const selectedIdAtStart=selected.value.nodeId;const providerId=selected.value.providerId;try{const r=await api.get(`/instances/${instanceId.value}/realms/${encodeURIComponent(realm.value)}/catalog`);const providers=[...(r.data.providers||[]),...(r.data.clientAuthenticatorProviders||[]),...(r.data.formActionProviders||[])];const p=providers.find((x:any)=>(x.id||x.providerId)===providerId);if(selectedId.value!==selectedIdAtStart)return;propertySchemas.value=p?.configDescription?.properties||[];const secretKeys=propertySchemas.value.filter((x:any)=>x.name&&(x.secret===true||String(x.secret).toLowerCase()==='true')).map((x:any)=>x.name);updateNode(selectedIdAtStart,n=>n.secretConfigKeys=secretKeys)}catch{propertySchemas.value=[]}}
function setConfig(key:string,value:any){updateNode(selected.value.nodeId,n=>{n.config={...(n.config||{}),[key]:value}})}
function saveRawConfig(){try{const value=JSON.parse(jsonConfig.value);if(!value||Array.isArray(value)||typeof value!=='object')throw Error();updateNode(selected.value.nodeId,n=>n.config=value);emit('message','Configuration JSON mise à jour.')}catch{emit('error','Configuration invalide : objet JSON clé/valeur attendu.')}}

function handleDesignerKeydown(event:KeyboardEvent){
 const target=event.target as HTMLElement|null
 const editing=!!target&&(target.isContentEditable||['INPUT','TEXTAREA','SELECT'].includes(target.tagName))
 if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='z'&&!editing){event.preventDefault();event.shiftKey?redo():undo();return}
 if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='y'&&!editing){event.preventDefault();redo();return}
 if(editing)return
 if((event.key==='Delete'||event.key==='Backspace')&&selectedId.value){event.preventDefault();deleteNode(selectedId.value)}
 else if(event.altKey&&event.key==='ArrowUp'){event.preventDefault();reorder(-1)}
 else if(event.altKey&&event.key==='ArrowDown'){event.preventDefault();reorder(1)}
 else if(event.key==='Escape')selectedId.value=null
}
onMounted(()=>window.addEventListener('keydown',handleDesignerKeydown))
onBeforeUnmount(()=>{window.removeEventListener('keydown',handleDesignerKeydown);if(historyTimer)clearTimeout(historyTimer)})
watch(()=>activeInsertionContext.value.executionKind,()=>{
 const available=quickCatalogEntries.value
 if(available.length&&!available.some((p:any)=>p.id===quickProviderId.value))quickProviderId.value=available[0].id
})
watch(()=>formActionProviders.value,()=>{
 if(activeInsertionContext.value.executionKind==='form-action'&&formActionCatalogEntries.value.length)quickProviderId.value=formActionCatalogEntries.value[0].id
})
</script>
<template>
 <div class="designer-meta panel">
  <div class="meta-field"><label>Type du flux<select :value="modelValue.flow.providerId||'basic-flow'" :disabled="(modelValue.flow.nodes||[]).length>0" @change="updateFlow('providerId',($event.target as HTMLSelectElement).value)"><option value="basic-flow">Flow standard (basic-flow)</option><option value="client-flow">Authentification client (client-flow)</option></select><small class="hint">Le type racine doit correspondre au catalogue d’exécutions : videz le flow avant de changer de type.</small></label></div>
  <div class="meta-field"><label>Instance Keycloak<select v-model="instanceId"><option value="">Mode hors ligne</option><option v-for="i in instances" :key="i.id" :value="i.id">{{i.name}}</option></select></label></div>
  <div class="meta-field"><label>Realm<select v-model="realm" :disabled="!instanceId"><option value="">Sélectionner</option><option v-for="r in realms" :key="r.realm" :value="r.realm">{{r.realm}}</option></select></label></div>
  <div class="meta-field import-field"><label>Importer un flow existant<select v-model="importAlias" :disabled="!realm"><option value="">Choisir un flow</option><option v-for="f in flows" :key="f.id" :value="f.alias">{{f.alias}}{{f.builtIn?' (natif)':''}}</option></select></label><div class="inline-actions"><button class="ghost" :disabled="!importAlias" @click="importSelected">Importer</button><button class="ghost" :disabled="!importAlias" @click="duplicateSelected">Dupliquer</button></div></div>
 </div>
 <details v-if="instanceId&&realm" class="flow-bindings-panel panel">
  <summary>Liaisons du Realm (Flow Bindings)</summary>
  <div class="flow-bindings-grid">
   <label v-for="binding in flowBindingFields" :key="binding.key">{{binding.label}}
    <select :value="flowBindings[binding.key]||''" :disabled="role!=='admin'" @change="flowBindings[binding.key]=($event.target as HTMLSelectElement).value||null">
     <option value="">— Conserver le binding actuel —</option>
     <template v-for="f in flows" :key="f.id"><option v-if="f.topLevel!==false && (binding.key==='clientAuthenticationFlow' ? f.providerId==='client-flow' : f.providerId==='basic-flow')" :value="f.alias">{{f.alias}}{{f.builtIn?' (natif)':''}}</option></template>
    </select>
   </label>
   <div class="flow-binding-actions"><span class="hint">La modification des bindings change immédiatement les flows utilisés par le Realm. Un compte administrateur KFD et des droits de gestion de Realm Keycloak sont nécessaires.</span><button class="primary" :disabled="role!=='admin'||bindingsSaving" @click="saveFlowBindings">{{bindingsSaving?'Enregistrement…':'Enregistrer les bindings'}}</button></div>
  </div>
 </details>
 <div class="project-fields panel"><label>Nom du projet<input :value="modelValue.project.name" @change="emitProject({...clone(),project:{...modelValue.project,name:($event.target as HTMLInputElement).value}})"></label><label>Alias Keycloak<input v-model="modelValue.flow.alias" @change="deployAlias=modelValue.flow.alias"></label><label>Description<input v-model="modelValue.flow.description"></label></div>
 <div class="designer-layout">
  <aside class="catalog panel">
   <div class="panel-title"><b>Composants Keycloak</b><button class="tiny" @click="showCatalog=!showCatalog">{{showCatalog?'−':'+'}}</button></div>
   <template v-if="showCatalog">
    <label class="template-picker">Modèles de départ<select v-model="templateSelection" @change="applyTemplate(templateSelection)"><option value="">Choisir un modèle…</option><option v-for="t in flowTemplates" :key="t.id" :value="t.id">{{t.label}}</option></select></label>
    <p class="hint">{{catalogSource==='keycloak'?'Catalogue découvert sur l’instance sélectionnée : providers intégrés et extensions installées.':'Catalogue local de départ ; connecter Keycloak pour découvrir tous les providers réellement installés.'}}</p><p class="hint">Famille active : <b>{{activeInsertionContext.executionKind}}</b> · conteneur : {{activeInsertionContext.label}}</p>
    <input v-model="catalogSearch" class="catalog-search" placeholder="Rechercher un composant…">
    <template v-if="activeInsertionContext.executionKind==='form-action'">
     <div class="catalog-section">FORM ACTIONS — FormActionFactory</div>
     <p class="hint">Ce sous-flow est un Form flow : il accepte des Form Actions, pas des Authenticators classiques. Chaque action expose REQUIRED ou DISABLED dans le modèle Keycloak.</p>
     <button v-for="c in filteredFormActionCatalog" :key="c.id" class="catalog-item" @click="addNode(c)"><span class="node-icon">▤</span><span><b>{{c.displayName}}</b><small>{{c.id}}</small></span><span class="plus">+</span></button>
     <p v-if="!filteredFormActionCatalog.length" class="hint">Aucune Form Action correspondante. Connectez Keycloak pour découvrir les FormActionFactory installées.</p>
    </template>
    <template v-else-if="activeInsertionContext.executionKind==='client-authenticator'">
     <div class="catalog-section">CLIENT AUTHENTICATORS</div>
     <button v-for="c in filteredClientCatalog" :key="c.id" class="catalog-item" @click="addNode(c)"><span class="node-icon">◇</span><span><b>{{c.displayName}}</b><small>{{c.id}}</small></span><span class="plus">+</span></button>
     <p v-if="!filteredClientCatalog.length" class="hint">Aucun client authenticator découvert pour cette instance. Utilisez un Provider ID personnalisé si nécessaire.</p>
    </template>
    <template v-else>
     <div class="catalog-section">AUTHENTICATORS ET CONDITIONS</div>
     <button v-for="c in filteredCatalog" :key="c.id" class="catalog-item" @click="addNode(c)"><span class="node-icon">◇</span><span><b>{{c.displayName}}</b><small>{{c.id}}</small></span><span class="plus">+</span></button>
     <p v-if="!filteredCatalog.length" class="hint">Aucun composant correspondant.</p>
     <div v-if="formProviders.length" class="form-provider-info"><div class="catalog-section">FORM AUTHENTICATORS (SPI)</div><p class="hint">Les FormAuthenticators sont des composants de rendu de formulaire ; les exécutions d’un Form flow sont ajoutées depuis la famille Form Actions.</p><div class="provider-info-group"><small v-for="p in formProviders" :key="p.id||p.providerId||p.name">{{p.displayName||p.name||p.id||p.providerId}}</small></div></div>
    </template>
    <button class="ghost full custom-provider-button" @click="customProviderOpen=true">+ Ajouter un Provider ID personnalisé</button>
    <div class="catalog-section">AJOUTER UN SOUS-FLOW</div>
    <button class="catalog-item" @click="addSubflow('basic')"><span class="node-icon">▱</span><span><b>Sous-flow Basic</b><small>Authenticators et requirements Basic</small></span><span class="plus">+</span></button>
    <button class="catalog-item" @click="addSubflow('form')" :disabled="activeInsertionContext.parentFlowProvider==='form-flow'||activeInsertionContext.parentFlowProvider==='client-flow'"><span class="node-icon">▤</span><span><b>Sous-flow Form</b><small>Form Action providers uniquement</small></span><span class="plus">+</span></button>
    <label class="file-import">Importer un projet JSON<input type="file" accept="application/json,.json" @change="importFile"></label>
   </template>
  </aside>
  <section class="canvas-wrap">
   <div class="canvas-toolbar">
    <div class="canvas-title"><b>{{modelValue.flow.alias}}</b><span class="muted"> · {{treeRows.length}} éléments</span><span v-if="modelValue.flow.builtIn" class="warning-tag">Flow natif</span></div>
    <div class="toolbar-actions">
     <label class="axis-picker">Sens<select v-model="layoutAxis"><option value="TB">Haut → bas</option><option value="LR">Gauche → droite</option></select></label>
     <div class="canvas-add-actions"><select v-model="quickProviderId" aria-label="Composant à ajouter"><option v-for="c in quickCatalogEntries" :key="c.id" :value="c.id">{{c.displayName}}</option></select><button class="primary" @click="addQuickProvider">+ Ajouter</button><select v-model="newSubflowType" aria-label="Type du sous-flow"><option value="basic">Basic</option><option value="form">Form</option></select><select v-if="newSubflowType==='form'" v-model="selectedFormProviderId" aria-label="FormAuthenticator"><option v-for="provider in formProviderCatalogEntries" :key="provider.id" :value="provider.id">{{provider.displayName}}</option></select><button class="ghost" :disabled="activeInsertionContext.parentFlowProvider==='form-flow'||(activeInsertionContext.parentFlowProvider==='client-flow'&&newSubflowType==='form')|| (newSubflowType==='form'&&!selectedFormProviderId)" @click="addSubflow">+ Sous-flow</button></div>
     <button class="ghost" :disabled="!canUndo" title="Annuler (Ctrl+Z)" @click="undo">↶</button><button class="ghost" :disabled="!canRedo" title="Rétablir (Ctrl+Y)" @click="redo">↷</button>
     <button class="ghost" :disabled="!selectedId" @click="duplicateNodeSelected">Dupliquer</button><button class="danger" :disabled="!selectedId" @click="selectedId&&deleteNode(selectedId)">Supprimer</button>
     <button class="ghost" @click="validate">Valider</button><button class="ghost" @click="exportProject">JSON KFD</button><button class="ghost" @click="exportYaml">YAML KFD</button><button class="primary" @click="save">Enregistrer</button>
    </div>
   </div>
   <div class="flow-direction-banner"><b>Déroulement : {{directionLabel}}</b><span>Flèche bleue : étape suivante · flèche violette : entrée / retour d’un sous-flow · vert : début · rouge : fin. Les requirements déterminent la logique Keycloak, pas des transitions libres de type succès/échec.</span></div>
   <VueFlow :nodes="nodes" :edges="edges" fit-view-on-init :nodes-draggable="false" @init="onFlowInit" @node-click="onNodeClick">
    <Background/><MiniMap/><Controls/>
    <template #node-default="{data}">
     <div v-if="data.kind==='start'" class="flow-boundary flow-start"><span>●</span> DÉBUT DU FLOW<Handle type="source" :position="layoutAxis==='TB'?Position.Bottom:Position.Right" /></div>
     <div v-else-if="data.kind==='end'" class="flow-boundary flow-end">FIN DU FLOW <span>■</span><Handle type="target" :position="layoutAxis==='TB'?Position.Top:Position.Left" /></div>
     <div v-else class="flow-node" :class="{selected:selectedId===data.nodeId}">
      <Handle type="target" :position="layoutAxis==='TB'?Position.Top:Position.Left" />
      <div class="flow-node-heading"><span>ÉTAPE {{data.step}}</span><button type="button" class="node-delete" title="Supprimer cet élément" aria-label="Supprimer cet élément" @pointerdown.stop @mousedown.stop @click.stop.prevent="deleteNode(data.nodeId)">×</button></div>
      <b>{{data.label}}</b><small>{{data.detail}}</small>
      <div class="flow-node-footer"><span class="requirement-pill" :class="String(data.requirement).toLowerCase()">{{data.requirement}}</span><span>{{data.isSubflow?'SOUS-FLUX':'EXÉCUTION'}}</span></div>
      <Handle type="source" :position="layoutAxis==='TB'?Position.Bottom:Position.Right" />
     </div>
    </template>
   </VueFlow>
   <div v-if="!treeRows.length" class="empty-canvas"><b>Votre workflow est vide</b><span>Ajoutez un authenticator, une condition ou un sous-flux. Le parcours sera représenté de {{directionLabel}}.</span><div><button class="primary" @click="addQuickProvider">+ Ajouter {{quickProviderLabel}}</button><button class="ghost" @click="addSubflow('basic')">+ Sous-flow Basic</button><button class="ghost" :disabled="activeInsertionContext.parentFlowProvider==='form-flow'||activeInsertionContext.parentFlowProvider==='client-flow'" @click="addSubflow('form')">+ Sous-flow Form</button></div></div>
   <div class="tree-panel"><button class="tree-toggle" @click="treeExpanded=!treeExpanded">{{treeExpanded?'⌄':'›'}}　Arborescence ({{treeRows.length}})</button><div v-if="treeExpanded" class="tree-list"><div v-for="n in treeRows" :key="n.nodeId" class="tree-entry" :style="{marginLeft:(n.depth*18)+'px'}" draggable="true" @dragstart="draggedId=n.nodeId" @dragover.prevent @drop.stop.prevent="dropTree(n.nodeId)"><button class="tree-row" :class="{selected:selectedId===n.nodeId}" @click="chooseNode(n.nodeId)"><span>{{n.type==='subflow'?'▱':'◇'}}</span><span class="tree-row-name">{{n.displayName}}</span><small>{{n.requirement}}</small></button><button class="tree-delete" type="button" title="Supprimer cet élément" aria-label="Supprimer cet élément" @pointerdown.stop @mousedown.stop @click.stop.prevent="deleteNode(n.nodeId)">×</button></div></div></div>
  </section>
  <aside class="properties panel">
   <div class="panel-title"><b>Propriétés</b><span v-if="selected" class="tiny-label">{{selected.type==='subflow'?'Sous-flux':'Exécution'}}</span></div>
   <template v-if="selected">
    <label>Nom affiché<input :value="selected.displayName" disabled><small class="hint">Libellé du composant fourni par Keycloak ou le catalogue local.</small></label>
    <label>Requirement<select :value="selected.requirement" @change="updateNode(selected.nodeId,n=>n.requirement=($event.target as HTMLSelectElement).value)"><option v-for="choice in requirementChoices" :key="choice" :value="choice">{{choice}}</option></select><small class="hint">Required : doit réussir. Alternative : un seul élément alternatif doit réussir ; les alternatives peuvent être ignorées si un Required du même niveau réussit. Disabled : ignoré. Conditional : réservé aux sous-flux, activé si toutes ses conditions réussissent.</small></label>
    <div class="order-actions"><button class="ghost" @click="reorder(-1)">↑ Monter</button><button class="ghost" @click="reorder(1)">↓ Descendre</button><button class="danger" @click="deleteNode(selected.nodeId)">Supprimer</button></div>
    <p class="hint">Raccourcis : Suppr pour supprimer, Alt + ↑ / ↓ pour réordonner, Ctrl + Z / Ctrl + Y pour annuler / rétablir. La suppression est d’abord locale.</p><p class="hint">Contexte d’ajout : <b>{{selectedContext}}</b>. Un composant ajouté sera inséré après la sélection ; sélectionner un sous-flow ajoute à l’intérieur.</p>
    <template v-if="selected.type==='execution'">
     <label>Provider ID<input :value="selected.providerId" @change="changeProviderId(selected.nodeId,($event.target as HTMLInputElement).value)"></label>
     <div v-if="selected.level!==undefined||selected.index!==undefined||selected.userSetupAllowed!==undefined" class="execution-meta"><b>Métadonnées Keycloak</b><span v-if="selected.level!==undefined">Niveau : {{selected.level}}</span><span v-if="selected.index!==undefined">Index : {{selected.index}}</span><span v-if="selected.userSetupAllowed!==undefined">Configuration utilisateur autorisée : {{selected.userSetupAllowed?'Oui':'Non'}}</span><small>Informations retournées par l’API. Certains champs sont en lecture seule dans le modèle d’exécution REST.</small></div>
     <label>Alias de configuration<input :value="selected.configAlias||''" @input="updateNode(selected.nodeId,n=>n.configAlias=($event.target as HTMLInputElement).value)" placeholder="KFD - Nom de la configuration"></label>
     <template v-if="selected.configurable!==false">
      <template v-if="selected.executionKind==='authenticator'">
      <div class="config-heading">Référence d’authentification (AMR)</div>
      <label>Authenticator Reference<input :value="selected.config?.['default.reference.value']||''" @input="setConfig('default.reference.value',($event.target as HTMLInputElement).value)" placeholder="ex. pwd, otp, hwk"></label>
      <label>Authenticator Reference Max Age (secondes)<input type="number" min="0" :value="selected.config?.['default.reference.maxAge']||''" @input="setConfig('default.reference.maxAge',($event.target as HTMLInputElement).value)" placeholder="0 = valable uniquement pour cette authentification"></label>
      <p class="hint">Ces valeurs alimentent la claim OIDC amr si le client utilise le protocol mapper Authentication Method Reference. Elles sont optionnelles.</p>
      </template>
     <div class="config-heading">Configuration du provider</div>
     <p v-if="!propertySchemas.length" class="hint">Aucun schéma de configuration récupéré. Connectez Keycloak pour obtenir les champs définis par le provider, ou utilisez le JSON libre.</p>
     <template v-for="prop in propertySchemas" :key="prop.name">
      <label class="schema-field"><span>{{prop.label||prop.name}}<b v-if="prop.required"> *</b></span>
       <select v-if="String(prop.type).toLowerCase()==='list'&&prop.options" :value="selected.config?.[prop.name]??prop.defaultValue??''" :required="!!prop.required" :disabled="!!prop.readOnly" @change="setConfig(prop.name,($event.target as HTMLSelectElement).value)"><option value="">— Sélectionner —</option><option v-for="o in prop.options" :key="typeof o==='object'?(o.value||o.name):o" :value="typeof o==='object'?(o.value||o.name):o">{{typeof o==='object'?(o.label||o.name||o.value):o}}</option></select>
       <input v-else-if="String(prop.type).toLowerCase()==='boolean'" type="checkbox" :checked="String(selected.config?.[prop.name]??prop.defaultValue)==='true'" :disabled="!!prop.readOnly" @change="setConfig(prop.name,($event.target as HTMLInputElement).checked?'true':'false')">
       <input v-else-if="['long','integer','int','number','double'].includes(String(prop.type).toLowerCase())" type="number" :value="selected.config?.[prop.name]??prop.defaultValue??''" :required="!!prop.required" :readonly="!!prop.readOnly" @input="setConfig(prop.name,($event.target as HTMLInputElement).value)">
       <textarea v-else-if="['script','multiline','textarea'].includes(String(prop.type).toLowerCase())" rows="4" :value="selected.config?.[prop.name]??prop.defaultValue??''" :required="!!prop.required" :readonly="!!prop.readOnly" @input="setConfig(prop.name,($event.target as HTMLTextAreaElement).value)"></textarea>
       <input v-else :type="prop.secret?'password':'text'" :value="selected.config?.[prop.name]??prop.defaultValue??''" :required="!!prop.required" :readonly="!!prop.readOnly" @input="setConfig(prop.name,($event.target as HTMLInputElement).value)">
       <small class="hint">{{prop.helpText||''}}</small>
      </label>
     </template>
     <label>Configuration JSON<textarea v-model="jsonConfig" rows="7" spellcheck="false"></textarea></label><button class="ghost full" @click="saveRawConfig">Appliquer le JSON</button>
     </template>
    <template v-else>
     <label>Alias du sous-flow<input :value="selected.alias||selected.remoteAlias||''" @change="updateNode(selected.nodeId,n=>{n.alias=($event.target as HTMLInputElement).value.trim();n.displayName=n.alias||n.displayName})" placeholder="Généré automatiquement si vide"></label>
     <label>Type du sous-flow<select :value="selected.flowType||'basic'" :disabled="!!selected.remoteExecutionId" @change="changeSubflowType(selected.nodeId,($event.target as HTMLSelectElement).value)"><option value="basic">Basic flow</option><option value="form">Form flow</option></select><small class="hint">Le type d’un sous-flow déjà déployé n’est pas convertible en place par l’API d’exécution Keycloak. Pour le changer, supprimer puis recréer le sous-flow.</small></label>
     <label v-if="selected.flowType==='form'">FormAuthenticator<select :value="selected.formProviderId||'registration-page-form'" :disabled="!!selected.remoteExecutionId" @change="changeFormProvider(selected.nodeId,($event.target as HTMLSelectElement).value)"><option v-for="provider in formProviderCatalogEntries" :key="provider.id" :value="provider.id">{{provider.displayName}} — {{provider.id}}</option><option v-if="selected.formProviderId&&!formProviderCatalogEntries.some((p:any)=>p.id===selected.formProviderId)" :value="selected.formProviderId">{{selected.formProviderId}} (non découvert)</option></select><small class="hint">Le FormAuthenticator rend le formulaire ; les Form Actions sont les étapes placées à l’intérieur.</small></label>
     <label>Description<input :value="selected.description||''" @input="updateNode(selected.nodeId,n=>n.description=($event.target as HTMLInputElement).value)"></label>
     <p class="hint">Sélectionnez ce sous-flow puis ajoutez un composant pour créer son contenu. Un sous-flow Basic contient des Authenticators et peut être REQUIRED, ALTERNATIVE, CONDITIONAL ou DISABLED. Un sous-flow Form contient des Form Actions ; son requirement est limité à REQUIRED ou DISABLED. Les deux familles de providers ne sont pas interchangeables.</p>
    </template>
   </template>
   </template>
   <p v-else class="empty">Sélectionnez un composant dans le canvas ou l’arborescence.</p>
   <div v-if="validation" class="validation" :class="validation.valid?'ok':'bad'"><b>{{validation.valid?'Validation réussie':'Erreurs de validation'}}</b><p v-for="e in validation.errors" :key="e">{{e}}</p><p v-for="w in validation.warnings" :key="w">Attention : {{w}}</p></div>
  </aside>
 </div>
 <div class="deploy-panel panel"><div><b>Déploiement Keycloak</b><p class="hint">Les modifications distantes sont réservées au rôle administrateur. Une sauvegarde est créée avant mise à jour.</p></div><div class="deploy-controls"><select v-model="deployMode"><option value="create">Créer un nouveau flow</option><option value="update">Mettre à jour un flow personnalisé existant</option></select><input v-model="deployAlias" placeholder="Alias cible"><label class="check-inline"><input v-model="allowDeletes" type="checkbox"> Autoriser les suppressions distantes</label><button class="primary" :disabled="!canDeploy" @click="openDeploy">Prévisualiser et déployer</button></div></div>
 <div v-if="customProviderOpen" class="modal-backdrop"><form class="modal-card" @submit.prevent="createCustomProvider"><h3>Ajouter un composant Keycloak</h3><p>Ajoutez un provider qui n’apparaît pas dans le catalogue. Il sera créé dans la famille SPI du conteneur sélectionné : {{activeInsertionContext.executionKind}}. Son identifiant doit correspondre exactement à un provider disponible dans la version Keycloak cible.</p><label>Provider ID<input v-model="customProviderId" required placeholder="ex. mon-authenticator"></label><label>Nom affiché<input v-model="customProviderName" placeholder="Nom du composant"></label><div class="modal-actions"><button type="button" class="ghost" @click="customProviderOpen=false">Annuler</button><button type="submit" class="primary">Ajouter au workflow</button></div></form></div>
 <div v-if="deployOpen" class="modal-backdrop"><div class="modal-card"><h3>Prévisualisation du déploiement</h3><p>{{deploymentPreview?.summary}}</p><p><b>Instance :</b> {{instances.find(x=>x.id===instanceId)?.name}} · <b>Realm :</b> {{realm}}</p><p><b>Mode :</b> {{deployMode==='create'?'Création':'Mise à jour'}} · <b>Alias :</b> {{deployAlias}}</p><p><b>État :</b> {{deploymentPreview?.valid?'Validation réussie':'Déploiement bloqué'}}</p><div v-if="deploymentPreview?.errors?.length" class="preview-errors"><b>Erreurs</b><p v-for="e in deploymentPreview.errors" :key="e">{{e}}</p></div><div v-if="deploymentPreview?.warnings?.length" class="preview-warnings"><b>Avertissements</b><p v-for="w in deploymentPreview.warnings" :key="w">{{w}}</p></div><div v-if="deploymentPreview?.counts" class="preview-counts">Créations : {{deploymentPreview.counts.create}} · Modifications : {{deploymentPreview.counts.modify}} · Suppressions : {{deploymentPreview.counts.delete}}</div><p v-if="allowDeletes" class="warning-text">Les exécutions absentes du projet seront supprimées.</p><label>Saisir exactement l’alias cible pour confirmer<input v-model="confirmValue" :placeholder="deployAlias"></label><div class="modal-actions"><button class="ghost" @click="deployOpen=false">Fermer</button><button class="primary" :disabled="confirmValue!==deployAlias || deploymentPreview?.valid===false" @click="confirmDeploy">Confirmer le déploiement</button></div></div></div>
</template>
