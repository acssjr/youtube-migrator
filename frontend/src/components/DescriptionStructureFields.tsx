import { CommonStructure, VideoStructure } from '../services/descriptionStructure.mjs';
interface Props { common: CommonStructure; video?: VideoStructure; presets: {name:string; socialLinks?:string; institutionalText?:string}[]; onCommon: (patch: Partial<CommonStructure>) => void; onVideo: (patch: Partial<VideoStructure>) => void; onCompose: (all: boolean) => void; onSave: () => void; onSaveInstitution: () => void; disabled: boolean }
export function DescriptionStructureFields({common,video,presets,onCommon,onVideo,onCompose,onSave,onSaveInstitution,disabled}:Props) {
  return <section className="workspace-panel description-structure" aria-label="Estrutura da descrição">
    <div className="panel-top"><div><h2>Estrutura da descrição</h2><p>As redes da banda que toca aparecem primeiro; depois, as da 25 de Março. Personalize os blocos mesmo sem referência da música. Confira o resultado antes de publicar.</p></div></div>
    <fieldset disabled={disabled}>
      <h3>Redes da instituição principal</h3>
      <div className="structure-grid"><label>Nome da instituição principal<input value={common.mainName} onChange={e=>onCommon({mainName:e.target.value})}/></label><label>Instagram da instituição principal<input value={common.mainInstagram} placeholder="@usuario ou link do Instagram" onChange={e=>onCommon({mainInstagram:e.target.value})}/></label></div>
      <label>Chamada e outras redes da instituição principal<textarea rows={3} value={common.mainFollow} onChange={e=>onCommon({mainFollow:e.target.value})}/><small>Texto publicado sugerido, editável. Ao informar o Instagram acima, a chamada será montada com o nome e o link; acrescente outras redes neste texto.</small></label>
      <label>Playlists e projetos · bloco comum do lote<textarea rows={6} value={common.playlists} placeholder="Cole as chamadas e os links das playlists, no formato que deseja usar." onChange={e=>onCommon({playlists:e.target.value})}/></label>
      <button className="secondary-action" onClick={onSave}>Salvar estrutura para próximos lotes</button>
      {video && <><h3>Instituição deste vídeo</h3>
        <label>Usar cadastro salvo<select value="" onChange={e=>{const p=presets.find(p=>p.name===e.target.value);if(p)onVideo({ensemble:p.name,archive:p.name,includeArchive:true,guest:!/25 de mar[çc]o/i.test(p.name),socialText:p.socialLinks||'',history:p.institutionalText||''});}}><option value="">Escolha uma filarmônica cadastrada</option>{presets.map(p=><option key={p.name}>{p.name}</option>)}</select></label>
        <div className="structure-grid"><label>Filarmônica do vídeo<input value={video.ensemble} placeholder="Sugerida pelo título; confirme o nome" onChange={e=>onVideo({ensemble:e.target.value})}/></label><label>Instagram da banda convidada<input value={video.instagram} placeholder="@usuario ou link do Instagram" onChange={e=>onVideo({instagram:e.target.value})}/></label></div>
        <label className="structure-check"><input type="checkbox" checked={video.guest} onChange={e=>onVideo({guest:e.target.checked})}/>Incluir também as redes da banda convidada</label>
        <label>Chamada e outras redes da banda convidada<textarea rows={3} value={video.socialText} onChange={e=>onVideo({socialText:e.target.value})}/></label>
        <label className="structure-check"><input type="checkbox" checked={video.includeArchive} onChange={e=>onVideo({includeArchive:e.target.checked})}/>Incluir “Esta partitura pertence ao acervo da…”</label>
        <label>Instituição proprietária da partitura<input value={video.archive} placeholder="Sugerida pelo título; confirme quem possui a partitura" onChange={e=>onVideo({archive:e.target.value})}/></label>
        <small>O nome no título é uma sugestão, não uma confirmação da propriedade da partitura. Corrija este campo quando o acervo for de outra instituição.</small>
        <label>História da instituição · texto exato<textarea rows={5} value={video.history} placeholder="Cole o texto que deseja usar, com o cabeçalho Sobre a filarmônica se preferir." onChange={e=>onVideo({history:e.target.value})}/></label>
        <label>Obra, compositor e arranjador · texto exato<textarea rows={5} value={video.body} placeholder="O texto encontrado será preservado aqui. Você também pode preencher manualmente." onChange={e=>onVideo({body:e.target.value})}/></label>
        <button className="secondary-action" onClick={onSaveInstitution}>Salvar redes e história desta filarmônica</button>
      </>}
      <div className="structure-actions">{video && <button className="primary-action" onClick={()=>onCompose(false)}>Montar descrição deste vídeo</button>}<button className="secondary-action" onClick={()=>onCompose(true)}>Aplicar estrutura a todos os vídeos do lote</button></div>
      <small>Esses botões recompõem a prévia com os campos acima. A publicação continua no botão Publicar após sua revisão.</small>
    </fieldset>
  </section>;
}
