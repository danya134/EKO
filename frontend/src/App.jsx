import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  AlertIcon,
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
  Select,
  Text,
  Textarea,
  VStack,
} from '@chakra-ui/react'

const MIN_TAP_H = '44px'
const API_BASE = import.meta.env.VITE_API_BASE_URL || `http://${window.location.hostname}:8000`

const BRANCH_OPTIONS_FALLBACK = ['Філія 1', 'Філія 2', 'Філія 3']

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

function App() {
  const [branch, setBranch] = useState('')
  const [branchOptions, setBranchOptions] = useState(BRANCH_OPTIONS_FALLBACK)
  const [revision, setRevision] = useState('0')
  const [reportDate, setReportDate] = useState(isoToday())

  const [siteName, setSiteName] = useState('')
  const [siteOptions, setSiteOptions] = useState([])
  const [inspectionForm, setInspectionForm] = useState('позапланова')
  const [inspectorFullName, setInspectorFullName] = useState('')
  const [inspectorPosition, setInspectorPosition] = useState('Провідний Еколог')
  const [unitRepFullName, setUnitRepFullName] = useState('')
  const [unitRepPosition, setUnitRepPosition] = useState('Начальник дільниці')

  const [rows, setRows] = useState([emptyRow(1)])
  const [photos, setPhotos] = useState([])

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const fileInputRef = useRef(null)

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
      fd.append('branch', branch)
      fd.append('revision', revision)
      fd.append('report_date', reportDate)
      fd.append('site_name', siteName)
      fd.append('inspection_form', inspectionForm)
      fd.append('inspector_full_name', inspectorFullName)
      fd.append('inspector_position', inspectorPosition)
      fd.append('unit_representative_full_name', unitRepFullName)
      fd.append('unit_representative_position', unitRepPosition)

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
      downloadBlob(blob, 'Акт_ВЕК.pdf')
    } catch (e) {
      setError(e?.message || 'Помилка формування PDF')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Box bg="white" color="gray.900" minH="100vh">
      <Container maxW="md" py={4}>
        <VStack align="stretch" spacing={4}>
          <Box>
            <Heading size="md">Екологічний звіт (Акт перевірки)</Heading>
            <Text fontSize="sm" color="gray.600" mt={1}>
              Мобільна форма для генерації PDF
            </Text>
          </Box>

          {error ? (
            <Alert status="error" borderRadius="md">
              <AlertIcon />
              <Text fontSize="sm" wordBreak="break-word">
                {error}
              </Text>
            </Alert>
          ) : null}

          <Card variant="outline">
            <CardBody>
              <VStack align="stretch" spacing={3}>
                <Heading size="sm">Шапка</Heading>

                <FormControl>
                  <FormLabel>Філія</FormLabel>
                  <Input minH={MIN_TAP_H} value={branch} onChange={(e) => setBranch(e.target.value)} />
                  <Select
                    mt={2}
                    minH={MIN_TAP_H}
                    placeholder="Обрати філію зі списку"
                    onChange={(e) => {
                      if (e.target.value) setBranch(e.target.value)
                    }}
                    value=""
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
                    <Input minH={MIN_TAP_H} value={revision} onChange={(e) => setRevision(e.target.value)} />
                  </FormControl>
                  <FormControl>
                    <FormLabel>Дата</FormLabel>
                    <Input
                      minH={MIN_TAP_H}
                      type="date"
                      value={reportDate}
                      onChange={(e) => setReportDate(e.target.value)}
                    />
                  </FormControl>
                </HStack>
              </VStack>
            </CardBody>
          </Card>

          <Card variant="outline">
            <CardBody>
              <VStack align="stretch" spacing={3}>
                <Heading size="sm">Основні дані</Heading>

                <FormControl isRequired>
                  <FormLabel>Назва підрозділу</FormLabel>
                  <Input minH={MIN_TAP_H} value={siteName} onChange={(e) => setSiteName(e.target.value)} />
                  <Select
                    mt={2}
                    minH={MIN_TAP_H}
                    placeholder={siteOptions.length ? 'Обрати підрозділ зі списку' : 'Немає списку для цієї філії'}
                    onChange={(e) => {
                      if (e.target.value) setSiteName(e.target.value)
                    }}
                    value=""
                    isDisabled={!siteOptions.length}
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
                  <Select minH={MIN_TAP_H} value={inspectionForm} onChange={(e) => setInspectionForm(e.target.value)}>
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
                  />
                </FormControl>

                <FormControl>
                  <FormLabel>Посада еколога</FormLabel>
                  <Input
                    minH={MIN_TAP_H}
                    placeholder="Введіть посаду"
                    value={inspectorPosition}
                    onChange={(e) => setInspectorPosition(e.target.value)}
                  />
                </FormControl>

                <FormControl isRequired>
                  <FormLabel>ПІБ представника дільниці</FormLabel>
                  <Input
                    minH={MIN_TAP_H}
                    placeholder="Введіть ПІБ"
                    value={unitRepFullName}
                    onChange={(e) => setUnitRepFullName(e.target.value)}
                  />
                </FormControl>

                <FormControl>
                  <FormLabel>Посада представника дільниці</FormLabel>
                  <Input
                    minH={MIN_TAP_H}
                    placeholder="Введіть посаду"
                    value={unitRepPosition}
                    onChange={(e) => setUnitRepPosition(e.target.value)}
                  />
                </FormControl>
              </VStack>
            </CardBody>
          </Card>

          <Card variant="outline">
            <CardBody>
              <VStack align="stretch" spacing={3}>
                <HStack justify="space-between">
                  <Heading size="sm">Невідповідності</Heading>
                  <Button minH={MIN_TAP_H} colorScheme="blue" variant="outline" onClick={addRow}>
                    Додати рядок
                  </Button>
                </HStack>

                <VStack align="stretch" spacing={3}>
                  {rows.map((r, idx) => (
                    <Card key={idx} variant="outline" bg="gray.50">
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
                            <Textarea
                              minH="96px"
                              value={r.description}
                              onChange={(e) => updateRow(idx, { description: e.target.value })}
                            />
                          </FormControl>

                          <FormControl>
                            <FormLabel>Коригуюча дія</FormLabel>
                            <Textarea
                              minH="80px"
                              value={r.corrective_actions}
                              onChange={(e) => updateRow(idx, { corrective_actions: e.target.value })}
                            />
                          </FormControl>

                          <FormControl>
                            <FormLabel>Відповідальний</FormLabel>
                            <Input
                              minH={MIN_TAP_H}
                              value={r.responsible}
                              onChange={(e) => updateRow(idx, { responsible: e.target.value })}
                            />
                          </FormControl>

                          <FormControl>
                            <FormLabel>Термін</FormLabel>
                            <Input
                              minH={MIN_TAP_H}
                              type="date"
                              value={r.due_date}
                              onChange={(e) => updateRow(idx, { due_date: e.target.value })}
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

          <Card variant="outline">
            <CardBody>
              <VStack align="stretch" spacing={3}>
                <Heading size="sm">Фотофіксація</Heading>

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
                    bg="white"
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
            colorScheme="blue"
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
