// Global registry for model parameters with their types and configurations
export const parameterRegistry = {
  // Temperature controls randomness
  temperature: {
    type: 'slider',
    label: 'Temperature',
    default: 0.7,
    min: 0,
    max: 2,
    step: 0.1,
    hint: 'Controls randomness: 0 = deterministic, 2 = very random'
  },
  
  // Top-p nucleus sampling
  top_p: {
    type: 'slider',
    label: 'Top P',
    default: 1.0,
    min: 0,
    max: 1,
    step: 0.01,
    hint: 'Nucleus sampling: consider tokens with cumulative probability'
  },
  
  // Top-k sampling
  top_k: {
    type: 'slider',
    label: 'Top K',
    default: 50,
    min: 1,
    max: 100,
    step: 1,
    hint: 'Consider only the top K tokens'
  },
  
  // Maximum tokens
  max_tokens: {
    type: 'number',
    label: 'Max Tokens',
    default: 2048,
    min: 1,
    max: 32768,
    hint: 'Maximum number of tokens to generate'
  },
  
  max_output_tokens: {
    type: 'number',
    label: 'Max Output Tokens',
    default: 2048,
    min: 1,
    max: 32768,
    hint: 'Maximum number of output tokens'
  },
  
  // Frequency penalty
  frequency_penalty: {
    type: 'slider',
    label: 'Frequency Penalty',
    default: 0,
    min: -2,
    max: 2,
    step: 0.1,
    hint: 'Penalize tokens based on their frequency in the text'
  },
  
  // Presence penalty
  presence_penalty: {
    type: 'slider',
    label: 'Presence Penalty',
    default: 0,
    min: -2,
    max: 2,
    step: 0.1,
    hint: 'Penalize tokens based on whether they appear in the text'
  },
  
  // Repetition penalty
  repetition_penalty: {
    type: 'slider',
    label: 'Repetition Penalty',
    default: 1,
    min: 0.1,
    max: 2,
    step: 0.1,
    hint: 'Penalize repeated tokens'
  },
  
  // Seed for reproducibility
  seed: {
    type: 'number',
    label: 'Seed',
    default: null,
    nullable: true,
    hint: 'Random seed for reproducible results'
  },
  
  // Number of completions
  n: {
    type: 'number',
    label: 'Number of Completions',
    default: 1,
    min: 1,
    max: 10,
    hint: 'How many completions to generate'
  },
  
  // Best of
  best_of: {
    type: 'number',
    label: 'Best Of',
    default: 1,
    min: 1,
    max: 10,
    hint: 'Generate best_of completions and return the best'
  },
  
  // Stop sequences
  stop: {
    type: 'chips',
    label: 'Stop Sequences',
    default: [],
    hint: 'Sequences where the model will stop generating'
  },
  
  // Response format
  response_format: {
    type: 'select',
    label: 'Response Format',
    default: 'text',
    options: ['text', 'json_object'],
    hint: 'Format of the response'
  },
  
  // Stream
  stream: {
    type: 'switch',
    label: 'Stream',
    default: false,
    hint: 'Stream the response as it\'s generated'
  },
  
  // Logprobs
  logprobs: {
    type: 'switch',
    label: 'Log Probabilities',
    default: false,
    hint: 'Include log probabilities in the response'
  },
  
  // Echo
  echo: {
    type: 'switch',
    label: 'Echo',
    default: false,
    hint: 'Echo the prompt in the response'
  },
  
  // Tool choice
  tool_choice: {
    type: 'select',
    label: 'Tool Choice',
    default: 'auto',
    options: ['auto', 'none', 'required'],
    hint: 'How the model should use tools'
  },
  
  // Logit bias
  logit_bias: {
    type: 'json',
    label: 'Logit Bias',
    default: {},
    hint: 'Modify likelihood of specific tokens'
  },
  
  // User
  user: {
    type: 'text',
    label: 'User ID',
    default: '',
    hint: 'Unique identifier for the end-user'
  },
  
  // KoboldCPP specific parameters
  rep_pen: {
    type: 'slider',
    label: 'Repetition Penalty',
    default: 1.1,
    min: 1.0,
    max: 1.5,
    step: 0.01,
    hint: 'KoboldCPP repetition penalty'
  },
  
  rep_pen_range: {
    type: 'number',
    label: 'Repetition Penalty Range',
    default: 1024,
    min: 0,
    max: 4096,
    hint: 'How far back to check for repetitions'
  },
  
  typical: {
    type: 'slider',
    label: 'Typical Sampling',
    default: 1.0,
    min: 0.0,
    max: 1.0,
    step: 0.01,
    hint: 'Typical sampling value (1.0 = disabled)'
  },
  
  tfs: {
    type: 'slider',
    label: 'Tail Free Sampling',
    default: 1.0,
    min: 0.0,
    max: 1.0,
    step: 0.01,
    hint: 'Tail free sampling (1.0 = disabled)'
  },
  
  top_a: {
    type: 'slider',
    label: 'Top A',
    default: 0.0,
    min: 0.0,
    max: 1.0,
    step: 0.01,
    hint: 'Top-a sampling threshold'
  },
  
  mirostat: {
    type: 'select',
    label: 'Mirostat',
    default: 0,
    options: [0, 1, 2],
    hint: 'Mirostat sampling mode (0 = disabled)'
  },
  
  mirostat_tau: {
    type: 'slider',
    label: 'Mirostat Tau',
    default: 5.0,
    min: 0.0,
    max: 10.0,
    step: 0.1,
    hint: 'Mirostat target entropy'
  },
  
  mirostat_eta: {
    type: 'slider',
    label: 'Mirostat Eta',
    default: 0.1,
    min: 0.0,
    max: 1.0,
    step: 0.01,
    hint: 'Mirostat learning rate'
  },
  
  grammar: {
    type: 'text',
    label: 'Grammar',
    default: '',
    hint: 'GBNF grammar string for constrained generation'
  },
  
  // Ollama specific
  num_ctx: {
    type: 'number',
    label: 'Context Size',
    default: 2048,
    min: 128,
    max: 32768,
    hint: 'Size of the context window'
  },
  
  num_predict: {
    type: 'number',
    label: 'Number of Predictions',
    default: -1,
    min: -1,
    hint: 'Maximum number of tokens to predict (-1 = infinite)'
  },
  
  // OpenAI compatible endpoints
  suffix: {
    type: 'text',
    label: 'Suffix',
    default: '',
    hint: 'Text to append after the completion'
  },
  
  logit_bias_k: {
    type: 'number',
    label: 'Logit Bias K',
    default: 0,
    hint: 'Number of top tokens to apply bias to'
  },
  
  min_p: {
    type: 'slider',
    label: 'Min P',
    default: 0.0,
    min: 0.0,
    max: 1.0,
    step: 0.01,
    hint: 'Minimum probability threshold'
  },
  
  // Additional KoboldCpp parameters
  typical_p: {
    type: 'slider',
    label: 'Typical P',
    default: 1.0,
    min: 0.0,
    max: 1.0,
    step: 0.01,
    hint: 'Typical sampling value (1.0 = disabled)'
  },
  
  tfs_z: {
    type: 'slider',
    label: 'TFS Z',
    default: 1.0,
    min: 0.0,
    max: 1.0,
    step: 0.01,
    hint: 'Tail free sampling (1.0 = disabled)'
  },
  
  rep_pen_slope: {
    type: 'slider',
    label: 'Repetition Penalty Slope',
    default: 1.0,
    min: 0.0,
    max: 10.0,
    step: 0.1,
    hint: 'Slope for repetition penalty decay'
  },
  
  single_line: {
    type: 'switch',
    label: 'Single Line',
    default: false,
    hint: 'Stop generation at line break'
  },
  
  sampler_seed: {
    type: 'number',
    label: 'Sampler Seed',
    default: -1,
    min: -1,
    hint: 'Seed for sampling (-1 = random)'
  },
  
  use_default_badwordsids: {
    type: 'switch',
    label: 'Use Default Bad Words',
    default: false,
    hint: 'Apply default bad words filter'
  },
  
  dynatemp_exponent: {
    type: 'slider',
    label: 'Dynamic Temperature Exponent',
    default: 1.0,
    min: 0.0,
    max: 5.0,
    step: 0.1,
    hint: 'Exponent for dynamic temperature calculation'
  },
  
  smoothing_curve: {
    type: 'slider',
    label: 'Smoothing Curve',
    default: 1.0,
    min: 0.0,
    max: 10.0,
    step: 0.1,
    hint: 'Curve factor for smoothing'
  },
  
  banned_tokens: {
    type: 'chips',
    label: 'Banned Tokens',
    default: [],
    hint: 'List of banned token IDs'
  },
  
  sampler_priority: {
    type: 'chips',
    label: 'Sampler Priority',
    default: [],
    hint: 'Order of samplers to apply'
  },
  
  ignore_eos: {
    type: 'switch',
    label: 'Ignore EOS',
    default: false,
    hint: 'Continue generation past EOS token'
  },
  
  spaces_between_special_tokens: {
    type: 'switch',
    label: 'Spaces Between Special Tokens',
    default: true,
    hint: 'Add spaces between special tokens'
  },
  
  speculative_ngram: {
    type: 'switch',
    label: 'Speculative N-gram',
    default: false,
    hint: 'Enable speculative n-gram generation'
  },
  
  streaming: {
    type: 'switch',
    label: 'Streaming',
    default: false,
    hint: 'Enable streaming responses'
  },
  
  xtc_threshold: {
    type: 'slider',
    label: 'XTC Threshold',
    default: 0.1,
    min: 0.0,
    max: 1.0,
    step: 0.01,
    hint: 'Threshold for XTC sampling'
  },
  
  xtc_probability: {
    type: 'slider',
    label: 'XTC Probability',
    default: 0.0,
    min: 0.0,
    max: 1.0,
    step: 0.01,
    hint: 'Probability of applying XTC sampling'
  },
  
  dry_multiplier: {
    type: 'slider',
    label: 'DRY Multiplier',
    default: 0.0,
    min: 0.0,
    max: 5.0,
    step: 0.1,
    hint: 'Multiplier for DRY penalty'
  },
  
  dry_base: {
    type: 'slider',
    label: 'DRY Base',
    default: 1.75,
    min: 1.0,
    max: 10.0,
    step: 0.05,
    hint: 'Base value for DRY penalty calculation'
  },
  
  dry_allowed_length: {
    type: 'number',
    label: 'DRY Allowed Length',
    default: 2,
    min: 1,
    max: 100,
    hint: 'Allowed sequence length before DRY penalty'
  },
  
  dry_penalty_last_n: {
    type: 'number',
    label: 'DRY Penalty Last N',
    default: 0,
    min: 0,
    max: 4096,
    hint: 'Number of tokens to consider for DRY penalty (0 = all)'
  },
  
  dry_sequence_breakers: {
    type: 'chips',
    label: 'DRY Sequence Breakers',
    default: [],
    hint: 'Tokens that break DRY sequences'
  },
  
  // Anthropic specific
  top_p_k: {
    type: 'number',
    label: 'Top P K',
    default: 0,
    hint: 'Number of tokens to consider for top-p'
  },
  
  // Together AI / vLLM specific
  repetition_penalty_range: {
    type: 'number',
    label: 'Repetition Penalty Range',
    default: 1024,
    min: 0,
    hint: 'Range for applying repetition penalty'
  },
  
  // Local model specific
  use_beam_search: {
    type: 'switch',
    label: 'Use Beam Search',
    default: false,
    hint: 'Enable beam search instead of sampling'
  },
  
  num_beams: {
    type: 'number',
    label: 'Number of Beams',
    default: 1,
    min: 1,
    max: 10,
    hint: 'Number of beams for beam search'
  },
  
  do_sample: {
    type: 'switch',
    label: 'Do Sample',
    default: true,
    hint: 'Whether to use sampling; otherwise uses greedy decoding'
  },
  
  early_stopping: {
    type: 'switch',
    label: 'Early Stopping',
    default: false,
    hint: 'Stop when at least num_beams sentences are finished'
  },
  
  // Custom/experimental parameters
  dynatemp_range: {
    type: 'slider',
    label: 'Dynamic Temperature Range',
    default: 0.0,
    min: 0.0,
    max: 2.0,
    step: 0.1,
    hint: 'Range for dynamic temperature adjustment'
  },
  
  smoothing_factor: {
    type: 'slider',
    label: 'Smoothing Factor',
    default: 0.0,
    min: 0.0,
    max: 1.0,
    step: 0.01,
    hint: 'Quadratic sampling smoothing factor'
  },
  
  epsilon_cutoff: {
    type: 'slider',
    label: 'Epsilon Cutoff',
    default: 0.0,
    min: 0.0,
    max: 0.1,
    step: 0.001,
    hint: 'Epsilon cutoff for sampling'
  },
  
  eta_cutoff: {
    type: 'slider',
    label: 'Eta Cutoff',
    default: 0.0,
    min: 0.0,
    max: 0.1,
    step: 0.001,
    hint: 'Eta cutoff for sampling'
  }
}

// Helper to get parameter config with fallback
export function getParameterConfig(paramName) {
  // Check if we have a registered config
  if (parameterRegistry[paramName]) {
    return parameterRegistry[paramName]
  }
  
  // Fallback for unknown parameters
  // Try to guess the type based on the parameter name
  
  // Sampling-related parameters usually need sliders
  if (paramName.includes('penalty') || paramName.includes('temperature') || 
      paramName.includes('top_') || paramName.includes('_tau') || 
      paramName.includes('_eta') || paramName.includes('_factor') ||
      paramName.includes('typical') || paramName.includes('tfs') ||
      paramName.includes('_p') || paramName.includes('_cutoff')) {
    return {
      type: 'slider',
      label: formatParamName(paramName),
      default: paramName.includes('penalty') ? 1.0 : 0.0,
      min: paramName.includes('penalty') ? 0.1 : 0.0,
      max: paramName.includes('penalty') ? 2.0 : 1.0,
      step: 0.01,
      hint: `Configure ${formatParamName(paramName)}`
    }
  }
  
  // Number/count parameters
  if (paramName.includes('max_') || paramName.includes('_tokens') || 
      paramName.includes('count') || paramName.includes('limit') ||
      paramName.includes('num_') || paramName.includes('_size') ||
      paramName.includes('_length') || paramName.includes('_range') ||
      paramName.includes('beams') || paramName.includes('batch')) {
    return {
      type: 'number',
      label: formatParamName(paramName),
      default: paramName.includes('tokens') ? 1024 : 
                paramName.includes('beams') ? 1 : 
                paramName.includes('range') ? 1024 : 100,
      min: paramName.includes('num_predict') ? -1 : 0,
      hint: `Configure ${formatParamName(paramName)}`
    }
  }
  
  // Boolean switches
  if (paramName.includes('enable') || paramName.includes('use_') || 
      paramName.includes('is_') || paramName.includes('do_') ||
      paramName.includes('_enabled') || paramName.includes('_disabled') ||
      paramName === 'stream' || paramName === 'echo' ||
      paramName.includes('_mode') && !paramName.includes('mirostat')) {
    return {
      type: 'switch',
      label: formatParamName(paramName),
      default: false,
      hint: `Enable/disable ${formatParamName(paramName)}`
    }
  }
  
  // Select dropdowns for mode/type parameters
  if (paramName.includes('_mode') || paramName.includes('_type') ||
      paramName.includes('format') || paramName === 'mirostat') {
    return {
      type: 'select',
      label: formatParamName(paramName),
      default: paramName === 'mirostat' ? 0 : 'default',
      options: paramName === 'mirostat' ? [0, 1, 2] : ['default', 'custom'],
      hint: `Select ${formatParamName(paramName)}`
    }
  }
  
  // Grammar/pattern parameters
  if (paramName.includes('grammar') || paramName.includes('pattern') ||
      paramName.includes('regex') || paramName.includes('schema')) {
    return {
      type: 'text',
      label: formatParamName(paramName),
      default: '',
      hint: `Enter ${formatParamName(paramName)} pattern`
    }
  }
  
  // JSON parameters
  if (paramName.includes('_json') || paramName.includes('_object') ||
      paramName.includes('_dict') || paramName.includes('config')) {
    return {
      type: 'json',
      label: formatParamName(paramName),
      default: {},
      hint: `JSON configuration for ${formatParamName(paramName)}`
    }
  }
  
  // Default to text field
  return {
    type: 'text',
    label: formatParamName(paramName),
    default: '',
    hint: `Configure ${formatParamName(paramName)}`
  }
}

function formatParamName(param) {
  return param.split('_').map(word => 
    word.charAt(0).toUpperCase() + word.slice(1)
  ).join(' ')
}