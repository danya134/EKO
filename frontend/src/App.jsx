import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  AlertIcon,
  Badge,
  Box,
  Button,
  Card,
  CardBody,
  Container,
  Divider,
  FormControl,
  FormLabel,
  Heading,
  HStack,
  IconButton,
  Input,
  InputGroup,
  InputLeftElement,
  Radio,
  RadioGroup,
  Select,
  Text,
  Textarea,
  VStack,
} from '@chakra-ui/react'

const MIN_TAP_H = '44px'
const API_BASE = import.meta.env.VITE_API_BASE_URL || `http://${window.location.hostname}:8000`

// Витягує осмислений текст помилки з відповіді сервера, незалежно від формату:
// - DRF ValidationError -> JSON { field: ["msg", ...] }
// - Django DEBUG -> HTML-сторінка (беремо <title>)
// - Інше -> перші ~500 символів тексту або HTTP-код.
async function extractServerErrorMessage(res, contentType) {
  try {
    if (contentType.includes('application/json')) {
      const data = await res.json()
      if (data && typeof data === 'object') {
        const parts = []
        for (const [key, val] of Object.entries(data)) {
          const text = Array.isArray(val) ? val.join('; ') : String(val)
          parts.push(key === 'detail' || key === 'non_field_errors' ? text : `${key}: ${text}`)
        }
        if (parts.length) return parts.join('\n')
      }
    }
    const text = await res.text()
    if (contentType.includes('text/html')) {
      const titleMatch = text.match(/<title[^>]*>([^<]+)<\/title>/i)
      if (titleMatch && titleMatch[1]) {
        return `Сервер повернув помилку: ${titleMatch[1].trim()}`
      }
    }
    const trimmed = (text || '').trim()
    if (trimmed) return trimmed.slice(0, 500)
  } catch {
    // ignore — провалимось у дефолт нижче
  }
  return `HTTP ${res.status}`
}

const CARD_PROPS = {
  bg: 'white',
  borderColor: 'blackAlpha.200',
  overflow: 'hidden',
}
const INNER_CARD_PROPS = {
  variant: 'outline',
  bg: '#faf8f3',
  borderColor: 'blackAlpha.200',
  boxShadow: 'none',
}
const FIELD_PROPS = {
  bg: 'white',
  borderColor: 'blackAlpha.300',
  _hover: { borderColor: 'blackAlpha.500' },
}
/** Як кнопка «Додати рядок» у блоці невідповідностей (блок 3) */
const ADD_ROW_BUTTON_PROPS = {
  minH: MIN_TAP_H,
  type: 'button',
  bg: '#2f4f6f',
  color: 'white',
  _hover: { bg: '#263f59' },
  alignSelf: 'flex-start',
}

const BRANCH_OPTIONS_FALLBACK = ['Філія 1', 'Філія 2', 'Філія 3']
const NONCONFORMITY_DESCRIPTIONS_FALLBACK = [
  'Відсутнє маркування тари/контейнерів для відходів',
  'Не ведеться журнал обліку відходів',
  'Порушено умови зберігання відходів (відсутнє накриття/піддон)',
]
const CORRECTIVE_ACTIONS_FALLBACK = [
  'Промаркувати тару/контейнери згідно вимог та розмістити таблички',
  'Відновити ведення журналу обліку та призначити відповідального',
  'Організувати місце зберігання: накриття, піддон, огородження',
]

const DOC_KIND = {
  ACT: 'act',
  REPORT: 'report',
}

/** Дата за замовчуванням для «Діє з» (04.06.2018 — як на типовому бланку). */
const DEFAULT_EFFECTIVE_FROM_DATE = '2018-06-04'

/** Рядок для шапки PDF: Діє з: "DD" "MM" YYYYр (типографські лапки). */
function effectiveFromLineFromIso(iso) {
  if (!iso || !/^\d{4}-\d{2}-\d{2}$/.test(iso)) return ''
  const [y, m, d] = iso.split('-')
  return `Діє з: \u201c${d}\u201d \u201c${m}\u201d ${y}р`
}

/**
 * Коригуюча дія за тим самим індексом у списках (як у JSON nonconformity_descriptions / corrective_actions).
 * Якщо текст порушення не збігається з пунктом каталогу — порожньо (лишаємо ручне заповнення).
 */
function suggestedCorrectiveForDescription(description, descOptions, corrOptions) {
  const d = (description || '').trim()
  if (!d || !Array.isArray(descOptions) || !Array.isArray(corrOptions)) return ''
  const idx = descOptions.findIndex((opt) => opt === d)
  if (idx < 0) return ''
  return (corrOptions[idx] || '').trim()
}

/** Лише для звіту Ф-15-02 — зберігається в corrective_actions */
const REPORT_STAGE_OPTIONS = ['виконано', 'не виконано', 'виконано неповністю']

function isoToday() {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function emptyRow(orderNumber) {
  return {
    order_number: orderNumber,
    description: '',
    corrective_actions: '',
    responsible: '',
    due_date: '',
    execution_percent: '100',
  }
}

function emptyAdditionalRep() {
  return { position: '', fullName: '' }
}

function emptyClosureRow() {
  return { corrective_action: '', completed: '', _srcDesc: '', _srcStage: '' }
}

function emptyAnalysisCauseRow() {
  return { violation: '', reason: '', corrective: '' }
}

function SectionHeader({ eyebrow, title, description }) {
  return (
    <VStack align="stretch" spacing={1}>
      <Badge
        alignSelf="flex-start"
        bg="#e9dfca"
        color="#4f432d"
        borderRadius="full"
        px={3}
        py={1}
        letterSpacing="0.08em"
      >
        {eyebrow}
      </Badge>
      <Heading size="md" color="#1f2933">
        {title}
      </Heading>
      {description ? (
        <Text fontSize="sm" color="gray.600">
          {description}
        </Text>
      ) : null}
    </VStack>
  )
}

function App() {
  const [docKind, setDocKind] = useState(DOC_KIND.ACT)
  const [branch, setBranch] = useState('')
  const [branchOptions, setBranchOptions] = useState(BRANCH_OPTIONS_FALLBACK)
  const [nonconformityDescriptionOptions, setNonconformityDescriptionOptions] = useState(NONCONFORMITY_DESCRIPTIONS_FALLBACK)
  const [correctiveActionOptions, setCorrectiveActionOptions] = useState(CORRECTIVE_ACTIONS_FALLBACK)
  const [revision, setRevision] = useState('0')
  const [effectiveFromDate, setEffectiveFromDate] = useState(DEFAULT_EFFECTIVE_FROM_DATE)
  const [reportDate, setReportDate] = useState(isoToday())
  /** Дата акта ВЕК у підставах звіту (текст «від …»); дата звіту — окремо в колонці таблиці */
  const [actDate, setActDate] = useState(isoToday())
  const [analysisProposedVek, setAnalysisProposedVek] = useState('')
  const [analysisProposedCheck, setAnalysisProposedCheck] = useState('')
  const [analysisActual, setAnalysisActual] = useState('')
  const [analysisCauseRows, setAnalysisCauseRows] = useState([emptyAnalysisCauseRow()])

  const [siteName, setSiteName] = useState('')
  const [siteOptions, setSiteOptions] = useState([])
  const [inspectionForm, setInspectionForm] = useState('позапланова')
  const [inspectorFullName, setInspectorFullName] = useState('')
  const [inspectorPosition, setInspectorPosition] = useState('Провідний Еколог')
  const [unitRepFullName, setUnitRepFullName] = useState('')
  const [unitRepPosition, setUnitRepPosition] = useState('Начальник дільниці')
  const [additionalReps, setAdditionalReps] = useState([])

  const [rows, setRows] = useState([emptyRow(1)])
  const [photos, setPhotos] = useState([])
  const [closureRows, setClosureRows] = useState([emptyClosureRow()])
  const [closureComments, setClosureComments] = useState('')

  const [availableResponsibles, setAvailableResponsibles] = useState([])

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const fileInputRef = useRef(null)
  // Початкові значення посад трактуємо як "автозаповнені" —
  // тоді при підвантаженні з JSON вони коректно перезаписуються.
  const lastAutoInspectorRef = useRef({ fullName: '', position: 'Провідний Еколог' })
  const lastAutoUnitRepRef = useRef({ fullName: '', position: 'Начальник дільниці' })
  const lastAutoResponsibleRef = useRef('')
  const lastAutoAdditionalRepsRef = useRef([])
  // Прапорці першого запуску ефектів — щоб не чистити поля на старті,
  // а лише при реальній зміні філії/дільниці.
  const isFirstBranchRunRef = useRef(true)
  const isFirstSiteNameRunRef = useRef(true)

  const onSelectDocKind = useCallback(
    (nextKind) => {
      if (nextKind === docKind) return
      // Щоб ефекти по філії/дільниці не «перезатирали» скидання дублюючими setState.
      isFirstBranchRunRef.current = true
      isFirstSiteNameRunRef.current = true

      setDocKind(nextKind)
      setError('')
      setBranch('')
      setSiteOptions([])
      setRevision('0')
      setEffectiveFromDate(DEFAULT_EFFECTIVE_FROM_DATE)
      setReportDate(isoToday())
      setActDate(isoToday())
      setAnalysisProposedVek('')
      setAnalysisProposedCheck('')
      setAnalysisActual('')
      setAnalysisCauseRows([emptyAnalysisCauseRow()])
      setSiteName('')
      setInspectionForm('позапланова')
      setInspectorFullName('')
      setInspectorPosition('Провідний Еколог')
      setUnitRepFullName('')
      setUnitRepPosition('Начальник дільниці')
      setAdditionalReps([])
      setRows([emptyRow(1)])
      setPhotos([])
      setClosureRows([emptyClosureRow()])
      setClosureComments('')
      setAvailableResponsibles([])

      lastAutoInspectorRef.current = { fullName: '', position: 'Провідний Еколог' }
      lastAutoUnitRepRef.current = { fullName: '', position: 'Начальник дільниці' }
      lastAutoResponsibleRef.current = ''
      lastAutoAdditionalRepsRef.current = []

      if (fileInputRef.current) fileInputRef.current.value = ''
    },
    [docKind]
  )

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/branches/`)
        if (!res.ok) return
        const data = await res.json()
        if (cancelled) return
        if (Array.isArray(data) && data.every((x) => typeof x === 'string')) {
          setBranchOptions(data)
        }
      } catch {
        // fallback залишається
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const formatResponsibleFromUnitRep = (pos, name) => {
    const p = (pos || '').trim()
    const n = (name || '').trim()
    if (p && n) return `${p} — ${n}`
    return (p || n || '').trim()
  }

  const applyAutofillPair = ({ incomingFullName, incomingPosition, setFullName, setPosition, lastRef }) => {
    const nextFullName = (incomingFullName || '').trim()
    const nextPosition = (incomingPosition || '').trim()
    if (!nextFullName && !nextPosition) return

    // Захоплюємо попередньо автозаповнені значення ДО викликів setState,
    // бо функціональний апдейтер може спрацювати після оновлення lastRef.current.
    const prevAutoFullName = (lastRef.current.fullName || '').trim()
    const prevAutoPosition = (lastRef.current.position || '').trim()

    setFullName((prev) => {
      const prevTrim = (prev || '').trim()
      if (!prevTrim || prevTrim === prevAutoFullName) return nextFullName || prevTrim
      return prev
    })
    setPosition((prev) => {
      const prevTrim = (prev || '').trim()
      if (!prevTrim || prevTrim === prevAutoPosition) return nextPosition || prevTrim
      return prev
    })

    lastRef.current = { fullName: nextFullName, position: nextPosition }
  }

  useEffect(() => {
    if (!isFirstBranchRunRef.current) {
      // Очищаємо залежні поля при зміні філії —
      // далі автозаповнення підвантажить нові значення з JSON.
      setSiteName('')
      setInspectorFullName('')
      setInspectorPosition('')
      lastAutoInspectorRef.current = { fullName: '', position: '' }
    }
    isFirstBranchRunRef.current = false
  }, [branch])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        if (!branch.trim()) return
        const siteTrim = (siteName || '').trim()
        const unitKnownForBranch =
          !siteTrim || !siteOptions.length || siteOptions.includes(siteName)
        const unitParam = unitKnownForBranch ? siteTrim : ''

        const url = new URL(`${API_BASE}/api/inspector-autofill/`)
        url.searchParams.set('branch', branch)
        if (unitParam) url.searchParams.set('unit', unitParam)
        const res = await fetch(url.toString())
        if (!res.ok) return
        const data = await res.json()
        if (cancelled) return
        applyAutofillPair({
          incomingFullName: data?.full_name,
          incomingPosition: data?.position,
          setFullName: setInspectorFullName,
          setPosition: setInspectorPosition,
          lastRef: lastAutoInspectorRef,
        })
      } catch {
        // ignore
      }
    })()
    return () => {
      cancelled = true
    }
  }, [branch, siteName, siteOptions])

  useEffect(() => {
    if (!isFirstSiteNameRunRef.current) {
      // Очищаємо залежні поля при зміні дільниці.
      // Поле "Відповідальний" у рядках чистимо лише якщо там стояло автозаповнене
      // значення — щоб не затирати ручні правки користувача.
      setUnitRepFullName('')
      setUnitRepPosition('')
      setAdditionalReps([])
      setAvailableResponsibles([])
      const prevAuto = (lastAutoResponsibleRef.current || '').trim()
      if (prevAuto) {
        setRows((prev) =>
          prev.map((r) => {
            const cur = (r.responsible || '').trim()
            if (cur && cur === prevAuto) return { ...r, responsible: '' }
            return r
          })
        )
      }
      lastAutoUnitRepRef.current = { fullName: '', position: '' }
      lastAutoAdditionalRepsRef.current = []
      lastAutoResponsibleRef.current = ''
    }
    isFirstSiteNameRunRef.current = false

    let cancelled = false
    ;(async () => {
      try {
        if (!branch.trim() || !siteName.trim()) return
        const url = new URL(`${API_BASE}/api/unit-representative-autofill/`)
        url.searchParams.set('branch', branch)
        url.searchParams.set('unit', siteName)
        const res = await fetch(url.toString())
        if (!res.ok) return
        const data = await res.json()
        if (cancelled) return

        const prevAutoResponsible = lastAutoResponsibleRef.current
        applyAutofillPair({
          incomingFullName: data?.full_name,
          incomingPosition: data?.position,
          setFullName: setUnitRepFullName,
          setPosition: setUnitRepPosition,
          lastRef: lastAutoUnitRepRef,
        })

        const staffList = Array.isArray(data?.staff) ? data.staff : []
        const incomingAdditionalReps = staffList
          .map((s) => ({
            position: ((s && s.position) || '').trim(),
            fullName: ((s && s.full_name) || '').trim(),
          }))
          .filter((r) => r.position || r.fullName)

        // Список усіх представників для випадайки "Відповідальний" (основний + додаткові).
        const responsibles = []
        const mainResp = formatResponsibleFromUnitRep(data?.position, data?.full_name)
        if (mainResp) responsibles.push(mainResp)
        for (const r of incomingAdditionalReps) {
          const f = formatResponsibleFromUnitRep(r.position, r.fullName)
          if (f && !responsibles.includes(f)) responsibles.push(f)
        }
        setAvailableResponsibles(responsibles)

        // Замінюємо попередньо автозаповнених додаткових представників —
        // тільки якщо користувач їх не редагував вручну.
        const prevAuto = lastAutoAdditionalRepsRef.current
        setAdditionalReps((prev) => {
          const sameAsAuto =
            prev.length === prevAuto.length &&
            prev.every((r, i) => {
              const a = prevAuto[i] || { position: '', fullName: '' }
              return (
                (r.position || '').trim() === (a.position || '').trim() &&
                (r.fullName || '').trim() === (a.fullName || '').trim()
              )
            })
          if (sameAsAuto) {
            return incomingAdditionalReps.map((r) => ({ ...r }))
          }
          return prev
        })
        lastAutoAdditionalRepsRef.current = incomingAdditionalReps.map((r) => ({ ...r }))

        const nextAutoResponsible = mainResp
        if (nextAutoResponsible) {
          lastAutoResponsibleRef.current = nextAutoResponsible
          setRows((prev) =>
            prev.map((r) => {
              const cur = (r.responsible || '').trim()
              if (!cur || cur === (prevAutoResponsible || '')) return { ...r, responsible: nextAutoResponsible }
              return r
            })
          )
        }
      } catch {
        // ignore
      }
    })()
    return () => {
      cancelled = true
    }
  }, [branch, siteName])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [descRes, actRes] = await Promise.all([
          fetch(`${API_BASE}/api/nonconformity-descriptions/`),
          fetch(`${API_BASE}/api/corrective-actions/`),
        ])
        if (!cancelled && descRes.ok) {
          const data = await descRes.json()
          if (Array.isArray(data) && data.every((x) => typeof x === 'string')) {
            setNonconformityDescriptionOptions(data)
          }
        }
        if (!cancelled && actRes.ok) {
          const data = await actRes.json()
          if (Array.isArray(data) && data.every((x) => typeof x === 'string')) {
            setCorrectiveActionOptions(data)
          }
        }
      } catch {
        // fallback залишається
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const url = new URL(`${API_BASE}/api/units/`)
        url.searchParams.set('branch', branch)
        const res = await fetch(url.toString())
        if (!res.ok) {
          if (!cancelled) setSiteOptions([])
          return
        }
        const data = await res.json()
        if (cancelled) return
        if (Array.isArray(data) && data.every((x) => typeof x === 'string')) {
          setSiteOptions(data)
        } else {
          setSiteOptions([])
        }
      } catch {
        if (!cancelled) setSiteOptions([])
      }
    })()
    return () => {
      cancelled = true
    }
  }, [branch])

  const [analysisSyncDeps, setAnalysisSyncDeps] = useState({
    rows: null,
    desc: null,
    act: null,
  })
  if (
    docKind === DOC_KIND.REPORT &&
    (analysisSyncDeps.rows !== rows ||
      analysisSyncDeps.desc !== nonconformityDescriptionOptions ||
      analysisSyncDeps.act !== correctiveActionOptions)
  ) {
    setAnalysisSyncDeps({
      rows,
      desc: nonconformityDescriptionOptions,
      act: correctiveActionOptions,
    })
    setAnalysisCauseRows((prev) => {
      const n = rows.length
      const next = []
      for (let i = 0; i < n; i++) {
        const descRaw = rows[i]?.description || ''
        const desc = descRaw.trim()
        const prevRow = prev[i]
        const prevV = (prevRow?.violation || '').trim()
        const sug = suggestedCorrectiveForDescription(
          descRaw,
          nonconformityDescriptionOptions,
          correctiveActionOptions
        )
        const reason = prevRow?.reason || ''
        let corrective = prevRow?.corrective || ''
        if (desc !== prevV) {
          corrective = sug || corrective
        } else if (sug && !corrective.trim()) {
          corrective = sug
        }
        next.push({
          violation: descRaw,
          reason,
          corrective,
        })
      }
      return next
    })
  }

  const [closureSyncDeps, setClosureSyncDeps] = useState({
    rows: null,
    desc: null,
    act: null,
  })
  if (
    docKind === DOC_KIND.REPORT &&
    (closureSyncDeps.rows !== rows ||
      closureSyncDeps.desc !== nonconformityDescriptionOptions ||
      closureSyncDeps.act !== correctiveActionOptions)
  ) {
    setClosureSyncDeps({
      rows,
      desc: nonconformityDescriptionOptions,
      act: correctiveActionOptions,
    })
    setClosureRows((prev) => {
      const n = rows.length
      const next = []
      for (let i = 0; i < n; i++) {
        const src = rows[i]
        const descRaw = src?.description || ''
        const desc = descRaw.trim()
        const stage = (src?.corrective_actions || '').trim()
        const sug = suggestedCorrectiveForDescription(
          descRaw,
          nonconformityDescriptionOptions,
          correctiveActionOptions
        )
        const prevRow = prev[i]
        const prevSrcDesc = (prevRow?._srcDesc || '').trim()
        const prevSrcStage = (prevRow?._srcStage || '').trim()

        let corrective_action = prevRow?.corrective_action || ''
        let completed = prevRow?.completed || ''

        if (desc !== prevSrcDesc) {
          corrective_action = sug || corrective_action
        } else if (sug && !corrective_action.trim()) {
          corrective_action = sug
        }

        if (stage !== prevSrcStage) {
          if (stage === 'виконано') completed = 'yes'
          else if (REPORT_STAGE_OPTIONS.includes(stage)) completed = 'no'
        }

        next.push({
          corrective_action,
          completed,
          _srcDesc: descRaw,
          _srcStage: stage,
        })
      }
      return next
    })
  }

  const canSubmit = useMemo(() => {
    return siteName.trim() && inspectionForm.trim() && inspectorFullName.trim() && unitRepFullName.trim()
  }, [siteName, inspectionForm, inspectorFullName, unitRepFullName])

  const addRow = () => {
    setRows((prev) => {
      const nextNum = prev.length + 1
      const newRow = emptyRow(nextNum)
      if (docKind === DOC_KIND.ACT) {
        const fromForm = formatResponsibleFromUnitRep(unitRepPosition, unitRepFullName).trim()
        const fromRef = (lastAutoResponsibleRef.current || '').trim()
        newRow.responsible = fromForm || fromRef
      }
      return [...prev, newRow]
    })
  }

  const removeRow = (idx) => {
    setRows((prev) => {
      const next = prev.filter((_, i) => i !== idx)
      return next.map((r, i) => ({ ...r, order_number: i + 1 }))
    })
  }

  const updateRow = (idx, patch) => {
    setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)))
  }

  const addAdditionalRep = () => {
    setAdditionalReps((prev) => [...prev, emptyAdditionalRep()])
  }

  const removeAdditionalRep = (idx) => {
    setAdditionalReps((prev) => prev.filter((_, i) => i !== idx))
  }

  const updateAdditionalRep = (idx, patch) => {
    setAdditionalReps((prev) => prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)))
  }

  const onPhotosChange = (e) => {
    const files = Array.from(e.target.files || [])
    if (!files.length) return
    setPhotos((prev) => [...prev, ...files])
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const openPhotoPicker = () => {
    fileInputRef.current?.click()
  }

  const resetPhotos = () => {
    setPhotos([])
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const updateClosureRow = (idx, patch) => {
    setClosureRows((prev) => prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)))
  }

  const updateAnalysisCauseRow = (idx, patch) => {
    setAnalysisCauseRows((prev) => prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)))
  }

  const downloadBlob = (blob, filename) => {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  const submit = async () => {
    setSubmitting(true)
    setError('')
    try {
      const fd = new FormData()
      fd.append('doc_kind', docKind)
      fd.append('branch', branch)
      fd.append('revision', revision)
      fd.append('effective_from', effectiveFromLineFromIso(effectiveFromDate))
      fd.append('report_date', reportDate)
      fd.append('act_date', docKind === DOC_KIND.REPORT ? actDate : reportDate)
      fd.append('site_name', siteName)
      fd.append('inspection_form', inspectionForm)
      fd.append('inspector_full_name', inspectorFullName)
      fd.append('inspector_position', inspectorPosition)
      fd.append('unit_representative_full_name', unitRepFullName)
      fd.append('unit_representative_position', unitRepPosition)
      const additionalPayload = additionalReps
        .map((r) => ({
          position: (r.position || '').trim(),
          full_name: (r.fullName || '').trim(),
        }))
        .filter((r) => r.position || r.full_name)
      fd.append('additional_unit_representatives_json', JSON.stringify(additionalPayload))

      const normalizedRows = rows
        .filter((r) => {
          if (docKind === DOC_KIND.REPORT) {
            return (
              r.description.trim() ||
              r.corrective_actions.trim() ||
              r.execution_percent?.trim() ||
              r.responsible.trim() ||
              r.due_date
            )
          }
          return r.description.trim() || r.corrective_actions.trim() || r.responsible.trim() || r.due_date
        })
        .map((r, i) => ({
          ...r,
          order_number: i + 1,
          due_date: r.due_date || null,
          execution_percent: (r.execution_percent ?? '').trim(),
        }))
      fd.append('nonconformities_json', JSON.stringify(normalizedRows))

      fd.append('analysis_proposed_vek', analysisProposedVek)
      fd.append('analysis_proposed_check', analysisProposedCheck)
      fd.append('analysis_actual', analysisActual)
      const firstCause = analysisCauseRows[0] || emptyAnalysisCauseRow()
      fd.append('analysis_reason_text', (firstCause.reason || '').trim())
      fd.append('analysis_violation', (firstCause.violation || '').trim())
      fd.append('analysis_corrective_action', (firstCause.corrective || '').trim())
      if (docKind === DOC_KIND.REPORT) {
        const causePayload = analysisCauseRows
          .map((r) => ({
            violation: (r.violation || '').trim(),
            reason: (r.reason || '').trim(),
            corrective: (r.corrective || '').trim(),
          }))
          .filter((r) => r.violation || r.reason || r.corrective)
        fd.append('analysis_cause_rows_json', JSON.stringify(causePayload))
        const closurePayload = closureRows
          .map((r) => ({
            corrective_action: (r.corrective_action || '').trim(),
            completed: (r.completed || '').trim(),
          }))
          .filter((r) => r.corrective_action || r.completed)
        fd.append('closure_rows_json', JSON.stringify(closurePayload))
        fd.append('closure_comments', closureComments)
      }

      if (docKind === DOC_KIND.ACT) {
        for (const f of photos) {
          fd.append('photos', f, f.name)
        }
      }

      const res = await fetch(`${API_BASE}/api/generate-pdf/`, {
        method: 'POST',
        body: fd,
      })

      const contentType = (res.headers.get('content-type') || '').toLowerCase()

      if (!res.ok) {
        throw new Error(await extractServerErrorMessage(res, contentType))
      }

      if (!contentType.includes('application/pdf')) {
        // Бек відповів 200, але це не PDF — найімовірніше HTML-сторінка помилки.
        throw new Error(await extractServerErrorMessage(res, contentType))
      }

      const blob = await res.blob()
      downloadBlob(blob, docKind === DOC_KIND.REPORT ? 'Звіт_Ф-15-02.pdf' : 'Акт_ВЕК.pdf')
    } catch (e) {
      setError(e?.message || 'Помилка формування PDF')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Box
      bg="linear-gradient(180deg, #f4f1ec 0%, #ebe4d8 100%)"
      color="gray.900"
      minH="100vh"
      py={{ base: 4, md: 8 }}
    >
      <Container maxW="3xl" px={{ base: 3, md: 6 }}>
        <VStack align="stretch" spacing={5}>
          <Box bg="#1f2933" color="white" borderRadius="28px" px={{ base: 5, md: 8 }} py={{ base: 6, md: 8 }}>
            <HStack
              justify="center"
              mt={0}
              spacing={{ base: 1, md: 3 }}
              bg="whiteAlpha.200"
              p="6px"
              borderRadius="full"
              w="full"
              flexWrap="nowrap"
            >
              <Button
                type="button"
                flex="1"
                minW="0"
                minH="56px"
                px={{ base: 2, md: 10 }}
                borderRadius="full"
                variant="ghost"
                fontSize={{ base: 'xs', sm: 'sm', md: 'lg' }}
                whiteSpace="normal"
                lineHeight="1.2"
                textAlign="center"
                bg={docKind === DOC_KIND.ACT ? 'white' : 'transparent'}
                color={docKind === DOC_KIND.ACT ? '#1f2933' : 'white'}
                _hover={{ bg: docKind === DOC_KIND.ACT ? 'white' : 'whiteAlpha.300' }}
                _active={{ bg: 'whiteAlpha.400' }}
                onClick={() => onSelectDocKind(DOC_KIND.ACT)}
              >
                Акт проведення перевірки
              </Button>
              <Button
                type="button"
                flex="1"
                minW="0"
                minH="56px"
                px={{ base: 2, md: 10 }}
                borderRadius="full"
                variant="ghost"
                fontSize={{ base: 'xs', sm: 'sm', md: 'lg' }}
                whiteSpace="normal"
                lineHeight="1.2"
                textAlign="center"
                bg={docKind === DOC_KIND.REPORT ? 'white' : 'transparent'}
                color={docKind === DOC_KIND.REPORT ? '#1f2933' : 'white'}
                _hover={{ bg: docKind === DOC_KIND.REPORT ? 'white' : 'whiteAlpha.300' }}
                _active={{ bg: 'whiteAlpha.400' }}
                onClick={() => onSelectDocKind(DOC_KIND.REPORT)}
              >
                Звіт з перевірки
              </Button>
            </HStack>
          </Box>

          {error ? (
            <Alert status="error" borderRadius="md">
              <AlertIcon />
              <Text fontSize="sm" wordBreak="break-word">
                {error}
              </Text>
            </Alert>
          ) : null}

          <Card variant="outline" {...CARD_PROPS}>
            <CardBody>
              <VStack align="stretch" spacing={4}>
                <SectionHeader
                  eyebrow="01"
                  title="Шапка документа"
                  description={
                    docKind === DOC_KIND.REPORT
                      ? 'Ф-15-02 — звіт з виконання перевірки.'
                      : 'Філія, редакція та дата акта.'
                  }
                />

                <FormControl>
                  <FormLabel>Філія</FormLabel>
                  <Input minH={MIN_TAP_H} value={branch} onChange={(e) => setBranch(e.target.value)} {...FIELD_PROPS} />
                  <Select
                    mt={2}
                    minH={MIN_TAP_H}
                    placeholder="Обрати філію зі списку"
                    onChange={(e) => {
                      if (e.target.value) setBranch(e.target.value)
                    }}
                    value=""
                    bg="white"
                    borderColor="blackAlpha.300"
                  >
                    {branchOptions.map((b) => (
                      <option key={b} value={b}>
                        {b}
                      </option>
                    ))}
                  </Select>
                </FormControl>

                <HStack spacing={3} align="start" flexWrap="wrap">
                  <FormControl>
                    <FormLabel>Редакція</FormLabel>
                    <Input minH={MIN_TAP_H} value={revision} onChange={(e) => setRevision(e.target.value)} {...FIELD_PROPS} />
                  </FormControl>
                  <FormControl>
                    <FormLabel>Діє з</FormLabel>
                    <InputGroup>
                      <InputLeftElement h={MIN_TAP_H} pointerEvents="none" color="#2f4f6f">
                        📅
                      </InputLeftElement>
                      <Input
                        minH={MIN_TAP_H}
                        type="date"
                        value={effectiveFromDate}
                        onChange={(e) => setEffectiveFromDate(e.target.value)}
                        pl={10}
                        {...FIELD_PROPS}
                      />
                    </InputGroup>
                  </FormControl>
                  {docKind === DOC_KIND.REPORT ? (
                    <FormControl>
                      <FormLabel>Дата складання акта</FormLabel>
                      <InputGroup>
                        <InputLeftElement h={MIN_TAP_H} pointerEvents="none" color="#2f4f6f">
                          📅
                        </InputLeftElement>
                        <Input
                          minH={MIN_TAP_H}
                          type="date"
                          value={actDate}
                          onChange={(e) => setActDate(e.target.value)}
                          pl={10}
                          {...FIELD_PROPS}
                        />
                      </InputGroup>
                    </FormControl>
                  ) : null}
                  <FormControl>
                    <FormLabel>{docKind === DOC_KIND.REPORT ? 'Дата звіту' : 'Дата'}</FormLabel>
                    <InputGroup>
                      <InputLeftElement h={MIN_TAP_H} pointerEvents="none" color="#2f4f6f">
                        📅
                      </InputLeftElement>
                      <Input
                        minH={MIN_TAP_H}
                        type="date"
                        value={reportDate}
                        onChange={(e) => setReportDate(e.target.value)}
                        pl={10}
                        {...FIELD_PROPS}
                      />
                    </InputGroup>
                  </FormControl>
                </HStack>
              </VStack>
            </CardBody>
          </Card>

          <Card variant="outline" {...CARD_PROPS}>
            <CardBody>
              <VStack align="stretch" spacing={4}>
                <SectionHeader
                  eyebrow="02"
                  title="Основні дані"
                  description={
                    docKind === DOC_KIND.REPORT
                      ? undefined
                      : 'Підрозділ, формат перевірки та відповідальні особи.'
                  }
                />

                <FormControl isRequired>
                  <FormLabel>Назва підрозділу</FormLabel>
                  <Input minH={MIN_TAP_H} value={siteName} onChange={(e) => setSiteName(e.target.value)} {...FIELD_PROPS} />
                  <Select
                    mt={2}
                    minH={MIN_TAP_H}
                    placeholder={siteOptions.length ? 'Обрати підрозділ зі списку' : 'Немає списку для цієї філії'}
                    onChange={(e) => {
                      if (e.target.value) setSiteName(e.target.value)
                    }}
                    value=""
                    isDisabled={!siteOptions.length}
                    bg="white"
                    borderColor="blackAlpha.300"
                  >
                    {siteOptions.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </Select>
                </FormControl>

                {docKind === DOC_KIND.ACT ? (
                  <FormControl isRequired>
                    <FormLabel>Форма перевірки</FormLabel>
                    <Select
                      minH={MIN_TAP_H}
                      value={inspectionForm}
                      onChange={(e) => setInspectionForm(e.target.value)}
                      bg="white"
                      borderColor="blackAlpha.300"
                    >
                      <option value="планова">планова</option>
                      <option value="позапланова">позапланова</option>
                    </Select>
                  </FormControl>
                ) : null}

                <FormControl isRequired>
                  <FormLabel>ПІБ перевіряючого</FormLabel>
                  <Input
                    minH={MIN_TAP_H}
                    placeholder="Введіть ПІБ"
                    value={inspectorFullName}
                    onChange={(e) => setInspectorFullName(e.target.value)}
                    {...FIELD_PROPS}
                  />
                </FormControl>

                <FormControl>
                  <FormLabel>Посада перевіряючого</FormLabel>
                  <Input
                    minH={MIN_TAP_H}
                    placeholder="Введіть посаду"
                    value={inspectorPosition}
                    onChange={(e) => setInspectorPosition(e.target.value)}
                    {...FIELD_PROPS}
                  />
                </FormControl>

                <FormControl isRequired>
                  <FormLabel>ПІБ представника дільниці</FormLabel>
                  <Input
                    minH={MIN_TAP_H}
                    placeholder="Введіть ПІБ"
                    value={unitRepFullName}
                    onChange={(e) => setUnitRepFullName(e.target.value)}
                    {...FIELD_PROPS}
                  />
                </FormControl>

                <FormControl>
                  <FormLabel>Посада представника дільниці</FormLabel>
                  <Input
                    minH={MIN_TAP_H}
                    placeholder="Введіть посаду"
                    value={unitRepPosition}
                    onChange={(e) => setUnitRepPosition(e.target.value)}
                    {...FIELD_PROPS}
                  />
                </FormControl>

                <VStack align="stretch" spacing={3}>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    minH={MIN_TAP_H}
                    alignSelf="flex-start"
                    onClick={addAdditionalRep}
                    borderColor="#2f4f6f"
                    color="#2f4f6f"
                  >
                    + Ще представник підрозділу
                  </Button>
                  {additionalReps.map((r, idx) => (
                    <Card key={idx} {...INNER_CARD_PROPS}>
                      <CardBody>
                        <VStack align="stretch" spacing={3}>
                          <HStack justify="space-between" align="center">
                            <Text fontWeight="600">Представник {idx + 2}</Text>
                            <IconButton
                              aria-label="Видалити"
                              minH={MIN_TAP_H}
                              size="sm"
                              variant="ghost"
                              icon={<span aria-hidden="true">✕</span>}
                              onClick={() => removeAdditionalRep(idx)}
                            />
                          </HStack>
                          <FormControl>
                            <FormLabel>Посада</FormLabel>
                            <Input
                              minH={MIN_TAP_H}
                              placeholder="Введіть посаду"
                              value={r.position}
                              onChange={(e) => updateAdditionalRep(idx, { position: e.target.value })}
                              {...FIELD_PROPS}
                            />
                          </FormControl>
                          <FormControl>
                            <FormLabel>ПІБ</FormLabel>
                            <Input
                              minH={MIN_TAP_H}
                              placeholder="Введіть ПІБ"
                              value={r.fullName}
                              onChange={(e) => updateAdditionalRep(idx, { fullName: e.target.value })}
                              {...FIELD_PROPS}
                            />
                          </FormControl>
                        </VStack>
                      </CardBody>
                    </Card>
                  ))}
                </VStack>
              </VStack>
            </CardBody>
          </Card>

          <Card variant="outline" {...CARD_PROPS}>
            <CardBody>
              <VStack align="stretch" spacing={4}>
                <SectionHeader
                  eyebrow="03"
                  title={docKind === DOC_KIND.REPORT ? 'Спостережувана невідповідність' : 'Невідповідності'}
                  description={
                    docKind === DOC_KIND.REPORT
                      ? 'Опис невідповідності, стадія та відсоток виконання.'
                      : undefined
                  }
                />

                <VStack align="stretch" spacing={3}>
                  {rows.map((r, idx) => (
                    <Card key={idx} {...INNER_CARD_PROPS}>
                      <CardBody>
                        <VStack align="stretch" spacing={3}>
                          <HStack justify="space-between" align="center">
                            <Text fontWeight="600">№ {r.order_number}</Text>
                            <IconButton
                              aria-label="Видалити"
                              minH={MIN_TAP_H}
                              size="sm"
                              variant="ghost"
                              icon={<span aria-hidden="true">✕</span>}
                              onClick={() => removeRow(idx)}
                              isDisabled={rows.length === 1}
                            />
                          </HStack>

                          <FormControl>
                            <FormLabel>
                              {docKind === DOC_KIND.REPORT ? 'Виявлена при ВЕК (опис)' : 'Опис порушення'}
                            </FormLabel>
                            <Select
                              minH={MIN_TAP_H}
                              placeholder="Обрати зі списку (або введіть вручну нижче)"
                              value=""
                              onChange={(e) => {
                                if (!e.target.value) return
                                const desc = e.target.value
                                const patch = { description: desc }
                                if (docKind === DOC_KIND.ACT) {
                                  const sug = suggestedCorrectiveForDescription(
                                    desc,
                                    nonconformityDescriptionOptions,
                                    correctiveActionOptions
                                  )
                                  if (sug) patch.corrective_actions = sug
                                }
                                updateRow(idx, patch)
                              }}
                              bg="white"
                              borderColor="blackAlpha.300"
                            >
                              {nonconformityDescriptionOptions.map((opt) => (
                                <option key={opt} value={opt}>
                                  {opt}
                                </option>
                              ))}
                            </Select>
                            <Textarea
                              minH="96px"
                              mt={2}
                              value={r.description}
                              onChange={(e) => updateRow(idx, { description: e.target.value })}
                              {...FIELD_PROPS}
                            />
                          </FormControl>

                          <FormControl>
                            <FormLabel>
                              {docKind === DOC_KIND.REPORT ? 'Стадія виконання' : 'Коригуюча дія'}
                            </FormLabel>
                            {docKind === DOC_KIND.REPORT ? (
                              <Select
                                minH={MIN_TAP_H}
                                placeholder="Оберіть стадію"
                                value={
                                  REPORT_STAGE_OPTIONS.includes((r.corrective_actions || '').trim())
                                    ? (r.corrective_actions || '').trim()
                                    : ''
                                }
                                onChange={(e) => updateRow(idx, { corrective_actions: e.target.value })}
                                bg="white"
                                borderColor="blackAlpha.300"
                              >
                                <option value="">Оберіть стадію</option>
                                {REPORT_STAGE_OPTIONS.map((opt) => (
                                  <option key={opt} value={opt}>
                                    {opt}
                                  </option>
                                ))}
                              </Select>
                            ) : (
                              <>
                                <Select
                                  minH={MIN_TAP_H}
                                  placeholder="Обрати зі списку (або введіть вручну нижче)"
                                  value=""
                                  onChange={(e) => {
                                    if (e.target.value) updateRow(idx, { corrective_actions: e.target.value })
                                  }}
                                  bg="white"
                                  borderColor="blackAlpha.300"
                                >
                                  {correctiveActionOptions.map((opt) => (
                                    <option key={opt} value={opt}>
                                      {opt}
                                    </option>
                                  ))}
                                </Select>
                                <Textarea
                                  minH="80px"
                                  mt={2}
                                  value={r.corrective_actions}
                                  onChange={(e) => updateRow(idx, { corrective_actions: e.target.value })}
                                  {...FIELD_PROPS}
                                />
                              </>
                            )}
                          </FormControl>

                          {docKind === DOC_KIND.REPORT ? (
                            <FormControl>
                              <FormLabel>Виконання, %</FormLabel>
                              <Input
                                minH={MIN_TAP_H}
                                placeholder="100"
                                inputMode="numeric"
                                value={r.execution_percent ?? '100'}
                                onChange={(e) => updateRow(idx, { execution_percent: e.target.value })}
                                {...FIELD_PROPS}
                              />
                            </FormControl>
                          ) : null}

                          {docKind === DOC_KIND.ACT ? (
                            <>
                              <FormControl>
                                <FormLabel>Відповідальний</FormLabel>
                                {availableResponsibles.length > 0 ? (
                                  <Select
                                    minH={MIN_TAP_H}
                                    placeholder="Обрати зі списку (або введіть вручну нижче)"
                                    value=""
                                    onChange={(e) => {
                                      if (e.target.value) updateRow(idx, { responsible: e.target.value })
                                    }}
                                    bg="white"
                                    borderColor="blackAlpha.300"
                                    mb={2}
                                  >
                                    {availableResponsibles.map((opt) => (
                                      <option key={opt} value={opt}>
                                        {opt}
                                      </option>
                                    ))}
                                  </Select>
                                ) : null}
                                <Input
                                  minH={MIN_TAP_H}
                                  value={r.responsible}
                                  onChange={(e) => updateRow(idx, { responsible: e.target.value })}
                                  {...FIELD_PROPS}
                                />
                              </FormControl>

                              <FormControl>
                                <FormLabel>Строк виконання</FormLabel>
                                <InputGroup>
                                  <InputLeftElement h={MIN_TAP_H} pointerEvents="none" color="#2f4f6f">
                                    📅
                                  </InputLeftElement>
                                  <Input
                                    minH={MIN_TAP_H}
                                    type="date"
                                    value={r.due_date}
                                    onChange={(e) => updateRow(idx, { due_date: e.target.value })}
                                    pl={10}
                                    {...FIELD_PROPS}
                                  />
                                </InputGroup>
                              </FormControl>
                            </>
                          ) : null}
                        </VStack>
                      </CardBody>
                    </Card>
                  ))}
                </VStack>

                <Button {...ADD_ROW_BUTTON_PROPS} onClick={addRow}>
                  Додати рядок
                </Button>
              </VStack>
            </CardBody>
          </Card>

          {docKind === DOC_KIND.REPORT ? (
            <Card variant="outline" {...CARD_PROPS}>
              <CardBody>
                <VStack align="stretch" spacing={4}>
                  <SectionHeader
                    eyebrow="04"
                    title="Аналіз причин невідповідностей"
                  />
                  <HStack spacing={3} align="start" flexWrap="wrap">
                    <FormControl>
                      <FormLabel>Запропонована дата: під час ВЕК</FormLabel>
                      <InputGroup>
                        <InputLeftElement h={MIN_TAP_H} pointerEvents="none" color="#2f4f6f">
                          📅
                        </InputLeftElement>
                        <Input
                          minH={MIN_TAP_H}
                          type="date"
                          value={analysisProposedVek}
                          onChange={(e) => setAnalysisProposedVek(e.target.value)}
                          pl={10}
                          {...FIELD_PROPS}
                        />
                      </InputGroup>
                    </FormControl>
                    <FormControl>
                      <FormLabel>Запропонована дата: при перевірці виконання</FormLabel>
                      <InputGroup>
                        <InputLeftElement h={MIN_TAP_H} pointerEvents="none" color="#2f4f6f">
                          📅
                        </InputLeftElement>
                        <Input
                          minH={MIN_TAP_H}
                          type="date"
                          value={analysisProposedCheck}
                          onChange={(e) => setAnalysisProposedCheck(e.target.value)}
                          pl={10}
                          {...FIELD_PROPS}
                        />
                      </InputGroup>
                    </FormControl>
                    <FormControl>
                      <FormLabel>Реальна дата виконання</FormLabel>
                      <InputGroup>
                        <InputLeftElement h={MIN_TAP_H} pointerEvents="none" color="#2f4f6f">
                          📅
                        </InputLeftElement>
                        <Input
                          minH={MIN_TAP_H}
                          type="date"
                          value={analysisActual}
                          onChange={(e) => setAnalysisActual(e.target.value)}
                          pl={10}
                          {...FIELD_PROPS}
                        />
                      </InputGroup>
                    </FormControl>
                  </HStack>

                  <VStack align="stretch" spacing={3}>
                    {analysisCauseRows.map((acr, idx) => (
                      <Card key={rows[idx]?.order_number ?? idx} {...INNER_CARD_PROPS}>
                        <CardBody>
                          <VStack align="stretch" spacing={3}>
                            <HStack justify="space-between" align="center">
                              <Text fontWeight="600">Рядок {idx + 1} (відповідає № {idx + 1} у блоці 03)</Text>
                            </HStack>

                            <FormControl>
                              <FormLabel>Порушення</FormLabel>
                              <Text fontSize="xs" color="gray.600" mb={1}>
                                Редагується у блоці «Спостережувана невідповідність»; тут лише для перегляду.
                              </Text>
                              <Textarea
                                minH="96px"
                                isReadOnly
                                cursor="default"
                                value={acr.violation}
                                bg="gray.50"
                                {...FIELD_PROPS}
                              />
                            </FormControl>

                            <FormControl>
                              <FormLabel>Причина</FormLabel>
                              <Textarea
                                minH="80px"
                                value={acr.reason}
                                onChange={(e) =>
                                  updateAnalysisCauseRow(idx, { reason: e.target.value })
                                }
                                placeholder="Вкажіть причину вручну"
                                {...FIELD_PROPS}
                              />
                            </FormControl>

                            <FormControl>
                              <FormLabel>Коригуюча дія</FormLabel>
                              <Select
                                minH={MIN_TAP_H}
                                placeholder="Обрати зі списку (як у акті)"
                                value=""
                                onChange={(e) => {
                                  if (e.target.value)
                                    updateAnalysisCauseRow(idx, { corrective: e.target.value })
                                }}
                                bg="white"
                                borderColor="blackAlpha.300"
                              >
                                {correctiveActionOptions.map((opt) => (
                                  <option key={opt} value={opt}>
                                    {opt}
                                  </option>
                                ))}
                              </Select>
                              <Textarea
                                minH="80px"
                                mt={2}
                                value={acr.corrective}
                                onChange={(e) =>
                                  updateAnalysisCauseRow(idx, { corrective: e.target.value })
                                }
                                {...FIELD_PROPS}
                              />
                            </FormControl>
                          </VStack>
                        </CardBody>
                      </Card>
                    ))}
                  </VStack>
                </VStack>
              </CardBody>
            </Card>
          ) : null}

          <Card variant="outline" {...CARD_PROPS}>
            <CardBody>
              <VStack align="stretch" spacing={4}>
                {docKind === DOC_KIND.REPORT ? (
                  <>
                    <SectionHeader
                      eyebrow="05"
                      title="Звіт про закриття невідповідностей"
                    />

                    <VStack align="stretch" spacing={4}>
                      {closureRows.map((r, idx) => (
                        <Box
                          key={rows[idx]?.order_number ?? idx}
                          borderWidth="1px"
                          borderColor="blackAlpha.200"
                          borderRadius="md"
                          p={3}
                          bg="#faf8f3"
                        >
                          <VStack align="stretch" spacing={3}>
                            <FormControl>
                              <FormLabel>Коригуюча дія</FormLabel>
                              <Select
                                minH={MIN_TAP_H}
                                placeholder="Оберіть зі списку (або введіть текст нижче)"
                                value=""
                                onChange={(e) => {
                                  if (e.target.value)
                                    updateClosureRow(idx, { corrective_action: e.target.value })
                                }}
                                bg="white"
                                borderColor="blackAlpha.300"
                              >
                                <option value="">—</option>
                                {correctiveActionOptions.map((opt) => (
                                  <option key={opt} value={opt}>
                                    {opt}
                                  </option>
                                ))}
                              </Select>
                              <Textarea
                                minH="80px"
                                mt={2}
                                value={r.corrective_action}
                                onChange={(e) =>
                                  updateClosureRow(idx, { corrective_action: e.target.value })
                                }
                                placeholder="Текст коригуючої дії (підставляється з блоці 03 за каталогом)"
                                {...FIELD_PROPS}
                              />
                            </FormControl>

                            <FormControl>
                              <FormLabel>Виконано</FormLabel>
                              <RadioGroup
                                value={r.completed}
                                onChange={(val) => updateClosureRow(idx, { completed: val })}
                              >
                                <HStack spacing={6}>
                                  <Radio value="yes">Так</Radio>
                                  <Radio value="no">Ні</Radio>
                                </HStack>
                              </RadioGroup>
                            </FormControl>
                          </VStack>
                        </Box>
                      ))}
                    </VStack>

                    <FormControl>
                      <FormLabel>Коментарі</FormLabel>
                      <Textarea
                        minH="96px"
                        value={closureComments}
                        onChange={(e) => setClosureComments(e.target.value)}
                        placeholder="Додаткові коментарі перевіряючого"
                        {...FIELD_PROPS}
                      />
                    </FormControl>
                  </>
                ) : (
                  <>
                    <SectionHeader
                      eyebrow="04"
                      title="Фотофіксація"
                      description="Додайте фото порушень до матеріалів акта."
                    />

                    <FormControl>
                      <FormLabel>Завантажити фото порушень</FormLabel>
                      <Input
                        ref={fileInputRef}
                        minH={MIN_TAP_H}
                        type="file"
                        multiple
                        accept="image/*"
                        onChange={onPhotosChange}
                        p={2}
                        {...FIELD_PROPS}
                      />
                      {photos.length ? (
                        <Text fontSize="sm" color="gray.600" mt={2}>
                          Обрано: {photos.length} фото
                        </Text>
                      ) : null}
                    </FormControl>

                    {photos.length ? (
                      <HStack flexWrap="wrap" spacing={3}>
                        <Button minH={MIN_TAP_H} type="button" variant="outline" onClick={openPhotoPicker}>
                          Додати ще фото
                        </Button>
                        <Button minH={MIN_TAP_H} variant="outline" onClick={resetPhotos}>
                          Очистити фото
                        </Button>
                      </HStack>
                    ) : null}
                  </>
                )}
              </VStack>
            </CardBody>
          </Card>

          <Divider />

          <Button
            minH={MIN_TAP_H}
            bg="#1f2933"
            color="white"
            _hover={{ bg: '#111827' }}
            size="lg"
            isLoading={submitting}
            loadingText="Формую PDF…"
            onClick={submit}
            isDisabled={!canSubmit || submitting}
          >
            Сформувати PDF
          </Button>
        </VStack>
      </Container>
    </Box>
  )
}

export default App
