import { useEffect, useMemo, useRef, useState } from 'react'
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
  Select,
  Text,
  Textarea,
  VStack,
} from '@chakra-ui/react'

const MIN_TAP_H = '44px'
const API_BASE = import.meta.env.VITE_API_BASE_URL || `http://${window.location.hostname}:8000`
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
  }
}

function emptyAdditionalRep() {
  return { position: '', fullName: '' }
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
  const [reportDate, setReportDate] = useState(isoToday())

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

    let cancelled = false
    ;(async () => {
      try {
        if (!branch.trim()) return
        const url = new URL(`${API_BASE}/api/inspector-autofill/`)
        url.searchParams.set('branch', branch)
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
  }, [branch])

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

  const canSubmit = useMemo(() => {
    return siteName.trim() && inspectionForm.trim() && inspectorFullName.trim() && unitRepFullName.trim()
  }, [siteName, inspectionForm, inspectorFullName, unitRepFullName])

  const addRow = () => {
    setRows((prev) => [...prev, emptyRow(prev.length + 1)])
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
    setPhotos(files)
  }

  const resetPhotos = () => {
    setPhotos([])
    if (fileInputRef.current) fileInputRef.current.value = ''
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
      fd.append('report_date', reportDate)
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
        .filter((r) => r.description.trim() || r.corrective_actions.trim() || r.responsible.trim() || r.due_date)
        .map((r, i) => ({
          ...r,
          order_number: i + 1,
          due_date: r.due_date || null,
        }))
      fd.append('nonconformities_json', JSON.stringify(normalizedRows))

      for (const f of photos) {
        fd.append('photos', f, f.name)
      }

      const res = await fetch(`${API_BASE}/api/generate-pdf/`, {
        method: 'POST',
        body: fd,
      })

      if (!res.ok) {
        const txt = await res.text()
        throw new Error(txt || `HTTP ${res.status}`)
      }

      const blob = await res.blob()
      downloadBlob(blob, docKind === DOC_KIND.REPORT ? 'Звіт_з_перевірки.pdf' : 'Акт_ВЕК.pdf')
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
              spacing={3}
              bg="whiteAlpha.200"
              p="6px"
              borderRadius="full"
              w="full"
              flexWrap="wrap"
            >
              <Button
                type="button"
                minH="56px"
                px={{ base: 6, md: 10 }}
                borderRadius="full"
                variant="ghost"
                fontSize={{ base: 'md', md: 'lg' }}
                bg={docKind === DOC_KIND.ACT ? 'white' : 'transparent'}
                color={docKind === DOC_KIND.ACT ? '#1f2933' : 'white'}
                _hover={{ bg: docKind === DOC_KIND.ACT ? 'white' : 'whiteAlpha.300' }}
                _active={{ bg: 'whiteAlpha.400' }}
                onClick={() => setDocKind(DOC_KIND.ACT)}
              >
                Акт проведення перевірки
              </Button>
              <Button
                type="button"
                minH="56px"
                px={{ base: 6, md: 10 }}
                borderRadius="full"
                variant="ghost"
                fontSize={{ base: 'md', md: 'lg' }}
                bg={docKind === DOC_KIND.REPORT ? 'white' : 'transparent'}
                color={docKind === DOC_KIND.REPORT ? '#1f2933' : 'white'}
                _hover={{ bg: docKind === DOC_KIND.REPORT ? 'white' : 'whiteAlpha.300' }}
                _active={{ bg: 'whiteAlpha.400' }}
                onClick={() => setDocKind(DOC_KIND.REPORT)}
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
                <SectionHeader eyebrow="01" title="Шапка документа" description="Філія, редакція та дата акта." />

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

                <HStack spacing={3} align="start">
                  <FormControl>
                    <FormLabel>Редакція</FormLabel>
                    <Input minH={MIN_TAP_H} value={revision} onChange={(e) => setRevision(e.target.value)} {...FIELD_PROPS} />
                  </FormControl>
                  <FormControl>
                    <FormLabel>Дата</FormLabel>
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
                  description="Підрозділ, формат перевірки та відповідальні особи."
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

                <FormControl isRequired>
                  <FormLabel>ПІБ еколога</FormLabel>
                  <Input
                    minH={MIN_TAP_H}
                    placeholder="Введіть ПІБ"
                    value={inspectorFullName}
                    onChange={(e) => setInspectorFullName(e.target.value)}
                    {...FIELD_PROPS}
                  />
                </FormControl>

                <FormControl>
                  <FormLabel>Посада еколога</FormLabel>
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
                <HStack justify="space-between">
                  <SectionHeader eyebrow="03" title="Невідповідності" />
                  <Button minH={MIN_TAP_H} bg="#2f4f6f" color="white" _hover={{ bg: '#263f59' }} onClick={addRow}>
                    Додати рядок
                  </Button>
                </HStack>

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
                            <FormLabel>Опис порушення</FormLabel>
                            <Select
                              minH={MIN_TAP_H}
                              placeholder="Обрати зі списку (або введіть вручну нижче)"
                              value=""
                              onChange={(e) => {
                                if (e.target.value) updateRow(idx, { description: e.target.value })
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
                            <FormLabel>Коригуюча дія</FormLabel>
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
                          </FormControl>

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
                            <FormLabel>Термін</FormLabel>
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
                <SectionHeader eyebrow="04" title="Фотофіксація" description="Додайте фото порушень до матеріалів акта." />

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
                  <Button minH={MIN_TAP_H} variant="outline" onClick={resetPhotos}>
                    Очистити фото
                  </Button>
                ) : null}
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

          <Text fontSize="xs" color="gray.500" textAlign="center">
            Запит відправляється на <Text as="span" fontFamily="mono">{API_BASE}/api/generate-pdf/</Text>
          </Text>
        </VStack>
      </Container>
    </Box>
  )
}

export default App
