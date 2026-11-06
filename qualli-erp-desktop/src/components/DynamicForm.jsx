// Erzeugt das Teilnehmerformular dynamisch aus /api/participants/config/fields.
import { useState } from 'react';

function optionValue(opt) {
  return typeof opt === 'object' ? opt.value : opt;
}
function optionText(opt) {
  return typeof opt === 'object' ? opt.label : opt;
}

function Field({ field, value, onChange, error }) {
  const id = `f-${field.name}`;
  const common = { id, name: field.name, 'aria-invalid': Boolean(error) };
  let input;
  switch (field.type) {
    case 'textarea':
      input = <textarea {...common} rows={3} value={value ?? ''} onChange={(e) => onChange(e.target.value)} />;
      break;
    case 'select':
      input = (
        <select {...common} value={value ?? ''} onChange={(e) => onChange(e.target.value)}>
          <option value="">– bitte wählen –</option>
          {field.options.map((o) => (
            <option key={optionValue(o)} value={optionValue(o)}>
              {optionText(o)}
            </option>
          ))}
        </select>
      );
      break;
    case 'multiselect': {
      const selected = Array.isArray(value) ? value : [];
      input = (
        <div className="chips" id={id}>
          {field.options.map((o) => {
            const v = optionValue(o);
            const on = selected.includes(v);
            return (
              <button
                type="button"
                key={v}
                className={`chip ${on ? 'chip-on' : ''}`}
                aria-pressed={on}
                onClick={() => onChange(on ? selected.filter((x) => x !== v) : [...selected, v])}
              >
                {optionText(o)}
              </button>
            );
          })}
        </div>
      );
      break;
    }
    case 'boolean':
      input = (
        <select {...common} value={value === true ? 'true' : value === false ? 'false' : ''} onChange={(e) => onChange(e.target.value === '' ? '' : e.target.value === 'true')}>
          <option value="">–</option>
          <option value="true">ja</option>
          <option value="false">nein</option>
        </select>
      );
      break;
    default: {
      const type = { date: 'date', email: 'email', tel: 'tel', number: 'number' }[field.type] || 'text';
      input = (
        <input
          {...common}
          type={type}
          min={field.min}
          max={field.max}
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value)}
        />
      );
    }
  }
  const wide = field.type === 'textarea' || field.type === 'multiselect';
  return (
    <div className={`form-field ${wide ? 'span-2' : ''}`}>
      <label htmlFor={id}>
        {field.label}
        {field.required && <span className="required"> *</span>}
      </label>
      {input}
      {error && <div className="field-error">{error}</div>}
    </div>
  );
}

/**
 * values: { basic_info: {...}, address_info: {...}, characteristics: {...} }
 * errors: { "basic_info.first_name": "..." }
 */
export default function DynamicForm({ config, values, onChange, errors = {} }) {
  const [openSection, setOpenSection] = useState(config.sections[0]?.id);
  return (
    <div className="dynamic-form">
      <div className="tabs" role="tablist">
        {config.sections.map((s) => {
          const hasError = Object.keys(errors).some((k) => k.startsWith(`${s.storage}.`));
          return (
            <button
              type="button"
              role="tab"
              key={s.id}
              aria-selected={openSection === s.id}
              className={`tab ${openSection === s.id ? 'tab-active' : ''} ${hasError ? 'tab-error' : ''}`}
              onClick={() => setOpenSection(s.id)}
            >
              {s.label}
            </button>
          );
        })}
      </div>
      {config.sections
        .filter((s) => s.id === openSection)
        .map((s) => (
          <div className="form-grid" key={s.id} role="tabpanel">
            {s.fields.map((f) => (
              <Field
                key={f.name}
                field={f}
                value={values[s.storage]?.[f.name]}
                error={errors[`${s.storage}.${f.name}`]}
                onChange={(v) => onChange({ ...values, [s.storage]: { ...(values[s.storage] || {}), [f.name]: v } })}
              />
            ))}
          </div>
        ))}
    </div>
  );
}
