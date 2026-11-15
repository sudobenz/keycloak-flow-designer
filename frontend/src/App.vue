<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import api from './api'
import Designer from './components/Designer.vue'
import { createUuid } from './utils/id'

const token=ref(localStorage.getItem('kfd_token')||'')
const username=ref('admin'), password=ref(''), role=ref('viewer'), error=ref(''), info=ref('')
const dark=ref(localStorage.getItem('kfd_theme')==='dark')
const page=ref<'designer'|'instances'|'projects'|'history'|'backups'|'audit'|'users'|'settings'>('designer')
const instances=ref<any[]>([]), projects=ref<any[]>([]), users=ref<any[]>([]), backups=ref<any[]>([]), auditEvents=ref<any[]>([])
const project=ref<any>(null)
const instanceForm=ref({name:'',base_url:'',token_url:'',client_id:'',client_secret:'',verify_tls:true})
const showInstanceForm=ref(false)
const userForm=ref({username:'',password:'',role:'editor'})
const currentPassword=ref(''),newPassword=ref(''),historyProjectId=ref(''),historyItems=ref<any[]>([])
const canAdmin=computed(()=>role.value==='admin')
function applyTheme(){document.documentElement.dataset.theme=dark.value?'dark':'light';localStorage.setItem('kfd_theme',dark.value?'dark':'light')}
function message(v:string){info.value=v;setTimeout(()=>{if(info.value===v)info.value=''},5000)}
async function login(){
 error.value=''
 try{
  const r=await api.post('/auth/login',{username:username.value,password:password.value})
  token.value=r.data.access_token
  role.value=r.data.role
  username.value=r.data.username
  localStorage.setItem('kfd_token',token.value)
  await loadAll()
 }catch(e:any){
  error.value=e.response?.data?.detail||'Connexion impossible'
 }
}
function logout(){
 token.value=''
 role.value='viewer'
 localStorage.removeItem('kfd_token')
 page.value='designer'
 project.value=null
 instances.value=[]
 projects.value=[]
 users.value=[]
 backups.value=[]
 auditEvents.value=[]
}
async function loadAll(){
 if(!token.value)return
 error.value=''
 try{
  // Validate the local application session first, before loading other resources.
  const me=await api.get('/auth/me')
  role.value=me.data.role
  username.value=me.data.username

  const [i,p]=await Promise.all([api.get('/instances'),api.get('/projects')])
  instances.value=i.data
  projects.value=p.data

  if(canAdmin.value){
   const [u,b,a]=await Promise.all([api.get('/users'),api.get('/backups'),api.get('/audit')])
   users.value=u.data
   backups.value=b.data
   auditEvents.value=a.data
  }else{
   users.value=[]
   backups.value=[]
   auditEvents.value=[]
  }
  if(!project.value)newProject()
 }catch(e:any){
  console.error('Échec du chargement initial de Keycloak Flow Designer:',e)
  if(e.response?.status===401){
   const endpoint=String(e.config?.url||'')
   let sessionInvalid=/\/auth\/me(?:\?|$)/.test(endpoint)

   // A 401 on another endpoint may come from Keycloak or a downstream operation.
   // Re-check /auth/me before deciding to sign the user out.
   if(!sessionInvalid){
    try{
     await api.get('/auth/me')
    }catch(validationError:any){
     sessionInvalid=validationError.response?.status===401
    }
   }

   if(sessionInvalid){
    logout()
    error.value='Session invalide ou expirée. Reconnectez-vous.'
   }else{
    const detail=e.response?.data?.detail||'Accès refusé par l’API.'
    error.value=`Une requête a été refusée (${endpoint}) : ${detail}. Votre session reste active.`
   }
  }else{
   const detail=e.response?.data?.detail||e.message||'Erreur inconnue'
   error.value=`Chargement de l’interface impossible : ${detail}`
  }
 }
}
function newProject(){project.value={schemaVersion:'1.0',project:{id:createUuid(),name:'Nouveau parcours',description:''},target:{},flow:{alias:'browser-custom',description:'',topLevel:true,providerId:'basic-flow',builtIn:false,nodes:[]}};page.value='designer'}
async function saved(p:any){project.value=p;await refreshProjects();message('Projet enregistré.')}
async function refreshProjects(){projects.value=(await api.get('/projects')).data}
async function refreshBackups(){if(canAdmin.value)backups.value=(await api.get('/backups')).data}
async function refreshAudit(){if(canAdmin.value)auditEvents.value=(await api.get('/audit')).data}
async function downloadBackup(id:string){const response=await api.get(`/backups/${id}/export.json`,{responseType:'blob'});const url=URL.createObjectURL(response.data);const a=document.createElement('a');a.href=url;a.download=`keycloak-backup-${id}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
async function openProject(id:string){project.value=(await api.get('/projects/'+id)).data;page.value='designer'}
async function openHistory(id:string){historyProjectId.value=id;historyItems.value=(await api.get(`/projects/${id}/history`)).data;page.value='history'}
async function restoreHistory(versionId:string){if(!confirm('Restaurer cette version du projet ? La version actuelle sera conservée dans l’historique.'))return;try{project.value=(await api.post(`/projects/${historyProjectId.value}/history/${versionId}/restore`)).data;await refreshProjects();historyItems.value=(await api.get(`/projects/${historyProjectId.value}/history`)).data;message('Version restaurée.');page.value='designer'}catch(e:any){error.value=e.response?.data?.detail||'Restauration impossible.'}}
async function addInstance(){error.value='';try{const form=instanceForm.value;if(!form.token_url)form.token_url=form.base_url.replace(/\/$/,'')+'/realms/master/protocol/openid-connect/token';await api.post('/instances',form);showInstanceForm.value=false;instanceForm.value={name:'',base_url:'',token_url:'',client_id:'',client_secret:'',verify_tls:true};await loadAll();message('Instance enregistrée.')}catch(e:any){error.value=e.response?.data?.detail||'Ajout de l’instance impossible.'}}
async function removeInstance(id:string){if(!confirm('Supprimer cette connexion ? Les projets JSON ne seront pas supprimés.'))return;await api.delete('/instances/'+id);await loadAll()}
async function addUser(){try{await api.post('/users',userForm.value);userForm.value={username:'',password:'',role:'editor'};users.value=(await api.get('/users')).data;message('Compte créé.')}catch(e:any){error.value=e.response?.data?.detail||'Création impossible.'}}
async function toggleUser(u:any){await api.patch(`/users/${encodeURIComponent(u.username)}/disabled?disabled=${!u.disabled}`);users.value=(await api.get('/users')).data}
async function changePassword(){try{await api.post('/auth/password',{currentPassword:currentPassword.value,newPassword:newPassword.value});currentPassword.value='';newPassword.value='';message('Mot de passe modifié.')}catch(e:any){error.value=e.response?.data?.detail||'Modification impossible.'}}
onMounted(()=>{applyTheme();if(token.value)loadAll()})
</script>
<template>
 <div v-if="!token" class="login-shell">
  <form class="login-card" @submit.prevent="login"><div class="brand-mark">K</div><div class="eyebrow">OUTIL D’INGÉNIERIE IAM</div><h1>Keycloak Flow Designer</h1><p>Concevoir, importer et déployer des parcours d’authentification.</p><label>Utilisateur<input v-model="username" autocomplete="username" required></label><label>Mot de passe<input v-model="password" type="password" autocomplete="current-password" required></label><button class="primary">Se connecter</button><p v-if="error" class="error">{{error}}</p><button type="button" class="theme-login ghost" @click="dark=!dark;applyTheme()">{{dark?'Passer au thème clair':'Passer au thème sombre'}}</button></form>
 </div>
 <div v-else class="app-shell">
  <header class="topbar"><div class="brand"><span class="brand-mark small">K</span><b>Keycloak Flow Designer</b><span class="version-tag">1.2.2</span></div><div class="top-actions"><span class="role-tag">{{role}}</span><span class="muted">{{username}}</span><button class="icon-btn" @click="dark=!dark;applyTheme()">{{dark?'☀':'◐'}}</button><button class="ghost" @click="logout">Déconnexion</button></div></header>
  <div class="layout"><aside class="sidebar"><div class="nav-title">ESPACE DE TRAVAIL</div><button :class="{active:page==='designer'}" @click="page='designer'">⌘　Designer</button><button :class="{active:page==='projects'}" @click="page='projects'">▤　Projets</button><button :class="{active:page==='instances'}" @click="page='instances'">◎　Instances Keycloak</button><button v-if="canAdmin" :class="{active:page==='backups'}" @click="page='backups';refreshBackups()">▣　Sauvegardes</button><button v-if="canAdmin" :class="{active:page==='audit'}" @click="page='audit';refreshAudit()">≡　Journal d’audit</button><button :class="{active:page==='users'}" @click="page='users'" v-if="canAdmin">♙　Utilisateurs</button><button :class="{active:page==='settings'}" @click="page='settings'">⚙　Compte</button><div class="sidebar-bottom"><span class="status-dot"></span> Persistance JSON active</div></aside>
   <main class="main">
    <div v-if="info" class="notice success-notice">{{info}}</div><div v-if="error" class="notice error-notice">{{error}}<button class="tiny" @click="error=''">×</button></div>
    <template v-if="page==='designer'"><div class="page-head"><div><div class="eyebrow">ÉDITEUR DE WORKFLOWS</div><h2>{{project?.project?.name||'Nouveau projet'}}</h2><p class="muted">Modèle local indépendant du serveur Keycloak.</p></div><div class="head-actions"><button class="ghost" @click="newProject">Nouveau</button><button class="primary" @click="page='projects'">Bibliothèque</button></div></div><Designer v-if="project" v-model="project" :instances="instances" :role="role" @saved="saved" @message="message" @error="error=$event" /></template>
    <template v-else-if="page==='instances'"><div class="page-head"><div><div class="eyebrow">CONNEXIONS</div><h2>Instances Keycloak</h2><p class="muted">Enregistrez les connexions techniques client_credentials.</p></div><button v-if="canAdmin" class="primary" @click="showInstanceForm=!showInstanceForm">{{showInstanceForm?'Fermer':'Ajouter une instance'}}</button></div>
     <form v-if="showInstanceForm" class="panel form-grid" @submit.prevent="addInstance"><label>Nom<input v-model="instanceForm.name" required></label><label>URL de base Admin REST<input v-model="instanceForm.base_url" placeholder="https://sso.example.net" required></label><label>URL Token<input v-model="instanceForm.token_url" placeholder="Automatique si vide"></label><label>Client ID<input v-model="instanceForm.client_id" required></label><label class="span-two">Client Secret<input v-model="instanceForm.client_secret" type="password" required></label><label class="checkbox-label"><input v-model="instanceForm.verify_tls" type="checkbox"> Vérifier le certificat TLS</label><div class="span-two"><button class="primary">Enregistrer l’instance</button></div></form>
     <div class="cards"><div v-for="i in instances" :key="i.id" class="panel instance-card"><div><b>{{i.name}}</b><p class="muted">{{i.base_url}}</p><small>Validation TLS : {{i.verify_tls?'Activée':'Désactivée'}}</small></div><div class="card-actions"><button class="ghost" @click="api.post('/instances/'+i.id+'/test').then(r=>message('Connexion OK — Keycloak '+(r.data.version||'version non détectée'))).catch(e=>error=e.response?.data?.detail||'Échec de connexion')">Tester</button><button v-if="canAdmin" class="danger" @click="removeInstance(i.id)">Supprimer</button></div></div><p v-if="!instances.length" class="empty">Aucune instance enregistrée.</p></div></template>
    <template v-else-if="page==='projects'"><div class="page-head"><div><div class="eyebrow">BIBLIOTHÈQUE</div><h2>Projets</h2><p class="muted">Workflows enregistrés sur le volume JSON.</p></div><button class="primary" @click="newProject">Nouveau projet</button></div><div class="cards"><div v-for="p in projects" :key="p.id" class="panel project-card"><button class="project-open" @click="openProject(p.id)"><b>{{p.name}}</b><small class="muted">{{p.realm||'Realm non défini'}} · {{p.updatedAt?new Date(p.updatedAt).toLocaleString('fr-FR'):''}}</small></button><div class="card-actions"><button class="ghost" @click="openHistory(p.id)">Versions</button><button class="danger" @click="api.delete('/projects/'+p.id).then(refreshProjects)">Supprimer</button></div></div><p v-if="!projects.length" class="empty">Aucun projet sauvegardé.</p></div></template>
    <template v-else-if="page==='audit'"><div class="page-head"><div><div class="eyebrow">TRAÇABILITÉ</div><h2>Journal d’audit</h2><p class="muted">Derniers événements de connexion, de modification et de déploiement.</p></div><button class="ghost" @click="refreshAudit">Actualiser</button></div><div class="panel audit-list"><div v-for="(ev,i) in auditEvents" :key="i" class="audit-row"><div><b>{{ev.action}}</b><small>{{ev.actor}} · {{ev.detail?.realm||ev.detail?.projectId||ev.detail?.instanceId||''}}</small></div><time>{{ev.at?new Date(ev.at).toLocaleString('fr-FR'):''}}</time></div><p v-if="!auditEvents.length" class="empty">Aucun événement enregistré.</p></div></template>
    <template v-else-if="page==='backups'"><div class="page-head"><div><div class="eyebrow">SNAPSHOTS KEYCLOAK</div><h2>Sauvegardes de déploiement</h2><p class="muted">Snapshots créés automatiquement avant les mises à jour de flows.</p></div><button class="ghost" @click="refreshBackups">Actualiser</button></div><div class="cards"><div v-for="b in backups" :key="b.id" class="panel instance-card"><div><b>{{b.alias}}</b><p class="muted">{{b.realm}} · {{b.createdAt?new Date(b.createdAt).toLocaleString('fr-FR'):''}}</p><small>{{b.instanceId||'Instance inconnue'}}</small></div><button class="primary" @click="downloadBackup(b.id)">Exporter le snapshot JSON</button></div><p v-if="!backups.length" class="empty">Aucune sauvegarde créée. Les snapshots sont générés avant les mises à jour de flows personnalisés.</p></div></template>
    <template v-else-if="page==='history'"><div class="page-head"><div><div class="eyebrow">HISTORIQUE DU PROJET</div><h2>Versions — {{historyProjectId}}</h2><p class="muted">Les versions sont conservées automatiquement lors des sauvegardes successives.</p></div><button class="ghost" @click="page='projects'">Retour aux projets</button></div><div class="cards"><div v-for="v in historyItems" :key="v.versionId" class="panel instance-card"><div><b>{{v.name}}</b><p class="muted">{{v.createdAt?new Date(v.createdAt).toLocaleString('fr-FR'):''}}</p><small>{{v.updatedBy?'Sauvegardé par '+v.updatedBy:'Version précédente'}}</small></div><button v-if="canAdmin" class="primary" @click="restoreHistory(v.versionId)">Restaurer cette version</button></div><p v-if="!historyItems.length" class="empty">Aucune ancienne version n’est encore disponible.</p></div></template>
    <template v-else-if="page==='users'"><div class="page-head"><div><div class="eyebrow">SÉCURITÉ LOCALE</div><h2>Utilisateurs</h2><p class="muted">Comptes locaux et rôles applicatifs.</p></div></div><div class="two-col"><form class="panel settings-card" @submit.prevent="addUser"><h3>Créer un compte</h3><label>Identifiant<input v-model="userForm.username" required minlength="3"></label><label>Mot de passe initial<input v-model="userForm.password" type="password" required minlength="12"></label><label>Rôle<select v-model="userForm.role"><option value="admin">Administrateur</option><option value="editor">Éditeur</option><option value="viewer">Lecteur</option></select></label><button class="primary">Créer le compte</button></form><div class="panel settings-card"><h3>Comptes existants</h3><div v-for="u in users" :key="u.username" class="user-row"><div><b>{{u.username}}</b><small>{{u.role}}</small></div><button class="ghost" :disabled="u.username===username" @click="toggleUser(u)">{{u.disabled?'Réactiver':'Désactiver'}}</button></div></div></div></template>
    <template v-else><div class="page-head"><div><div class="eyebrow">PRÉFÉRENCES</div><h2>Compte et apparence</h2></div></div><div class="panel settings-card"><h3>Apparence</h3><label>Thème<select v-model="dark" @change="applyTheme"><option :value="false">Clair</option><option :value="true">Sombre</option></select></label><hr><h3>Changer le mot de passe</h3><form @submit.prevent="changePassword"><label>Mot de passe actuel<input v-model="currentPassword" type="password" required></label><label>Nouveau mot de passe (12 caractères minimum)<input v-model="newPassword" type="password" required minlength="12"></label><button class="primary">Modifier le mot de passe</button></form></div></template>
   </main>
  </div>
 </div>
</template>
