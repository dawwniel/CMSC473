--[[
	Prompt2Particles importer

	Rebuilds Roblox particles from JSONL records (one JSON object per line,
	one line per ParticleEmitter). The module is pure: parsing, validation,
	building and diffing never touch the DataModel. Only executePlan() and
	apply(..., { commit = true }) change the place, and both are undoable.

	Record format (formatVersion 1):

	{
	  "formatVersion": 1,
	  "id": "SmokeRings/F021_V01_Base/ParticleEmitter",       -- path joined by "/"
	  "path": ["SmokeRings", "F021_V01_Base", "ParticleEmitter"], -- relative to the import root:
	                                                            -- ...folders, attachment, emitter
	  "attachment": <node>,   -- the emitter's parent (Attachment, Part, ...)
	  "emitter": <node>,      -- the ParticleEmitter itself
	  "prompt_gui": <node>,   -- optional; the Prompt BillboardGui and its children
	  "prompt": "...",        -- optional; used to build a default Prompt when prompt_gui is absent

	  -- Descriptive fields (family, feature_no, variant_no, variant_name,
	  -- playback_mode, row_hash, ...) are allowed and ignored by the builder.
	}

	<node> = {
	  "class": "ParticleEmitter",
	  "name": "ParticleEmitter",
	  "properties": { "<Property>": <value>, ... },
	  "attributes": { "<Attribute>": <value>, ... },
	  "children": [ <node>, ... ]
	}

	<value> is a JSON string, number or boolean, or a tagged object for Roblox types:

	  {"_type":"Vector3","value":[x,y,z]}           {"_type":"Vector2","value":[x,y]}
	  {"_type":"Color3","value":[r,g,b]}            (components 0..1)
	  {"_type":"UDim","value":[scale,offset]}       {"_type":"UDim2","value":[xs,xo,ys,yo]}
	  {"_type":"Rect","value":[minX,minY,maxX,maxY]}
	  {"_type":"CFrame","value":[x,y,z,r00,r01,r02,r10,r11,r12,r20,r21,r22]}
	  {"_type":"NumberRange","value":[min,max]}
	  {"_type":"NumberSequence","keypoints":[[time,value,envelope?],...]}
	  {"_type":"ColorSequence","keypoints":[[time,r,g,b],...]}
	  {"_type":"Enum","enum":"ParticleEmitterShape","value":"Box"}
	  {"_type":"BrickColor","value":"Bright red"}
	  {"_type":"Font","family":"rbxasset://...","weight":"Medium","style":"Normal"}
	  {"_type":"Content","uri":"rbxassetid://..."}
	  {"_type":"JSONString","value":<any JSON>}     (stored on the instance as encoded JSON text,
	                                                 e.g. the PromptAlternates attribute)

	New Roblox types are supported by adding an entry to Importer.decoders
	(and, if needed, a comparison in valuesEqual).

	Playback: an emitter whose EmitCount attribute is > 0 is a burst effect and
	only shows particles through Importer.emit(); otherwise it emits
	continuously at its Rate.
]]

local Importer = {}

Importer.FORMAT_VERSION = 1

-- Relative tolerance used when comparing numbers. Roblox stores most values
-- as 32-bit floats, so values read back rarely match JSON doubles exactly.
Importer.TOLERANCE = 1e-4

-- Upgrades a record from formatVersion N to N + 1: Importer.migrations[N] = function(record) ... end
Importer.migrations = {}

-- JSON and instance creation are swappable so the module can run outside Studio.
local HttpService = game and game:GetService("HttpService")

Importer.json = {
	decode = function(text)
		return HttpService:JSONDecode(text)
	end,
	encode = function(value)
		return HttpService:JSONEncode(value)
	end,
}

Importer.newInstance = function(className)
	return Instance.new(className)
end

local RESERVED_PROPERTIES = { Parent = true, ClassName = true, Name = true }

local ATTRIBUTE_TYPES = {
	string = true, boolean = true, number = true, UDim = true, UDim2 = true,
	BrickColor = true, Color3 = true, Vector2 = true, Vector3 = true, CFrame = true,
	NumberSequence = true, ColorSequence = true, NumberRange = true, Rect = true,
	Font = true, EnumItem = true,
}

-- Prompt GUI used when a record has prompt text but no prompt_gui node.
-- Matches the style of the existing dataset entries.
local function defaultPromptNode(text)
	return {
		class = "BillboardGui",
		name = "Prompt",
		properties = {
			Size = { _type = "UDim2", value = { 0, 175, 0, 76 } },
			StudsOffset = { _type = "Vector3", value = { 0, 10, 0 } },
			MaxDistance = 100,
			LightInfluence = 0,
			ClipsDescendants = true,
		},
		children = {
			{
				class = "TextLabel",
				name = "TextLabel",
				properties = {
					Size = { _type = "UDim2", value = { 1, 0, 1, 0 } },
					BackgroundColor3 = { _type = "Color3", value = { 0.0588235, 0.0823529, 0.117647 } },
					BackgroundTransparency = 0.25,
					BorderSizePixel = 0,
					TextColor3 = { _type = "Color3", value = { 1, 1, 1 } },
					TextWrapped = true,
					TextSize = 12,
					FontFace = {
						_type = "Font",
						family = "rbxasset://fonts/families/GothamSSm.json",
						weight = "Medium",
						style = "Normal",
					},
					Text = text,
				},
			},
		},
	}
end

--------------------------------------------------------------------------------
-- Small helpers
--------------------------------------------------------------------------------

local function sortedKeys(map)
	local keys = {}
	for key in pairs(map) do
		table.insert(keys, key)
	end
	table.sort(keys, function(a, b)
		return tostring(a) < tostring(b)
	end)
	return keys
end

local function isArray(value)
	if type(value) ~= "table" then
		return false
	end
	local count = 0
	for _ in pairs(value) do
		count += 1
	end
	return count == #value
end

local function append(list, items)
	for _, item in ipairs(items) do
		table.insert(list, item)
	end
end

local function near(a, b)
	return math.abs(a - b) <= Importer.TOLERANCE * math.max(1, math.abs(a), math.abs(b))
end

local function deepEqual(a, b)
	if type(a) ~= type(b) then
		return false
	end
	if type(a) == "number" then
		return near(a, b)
	end
	if type(a) ~= "table" then
		return a == b
	end
	for key, value in pairs(a) do
		if not deepEqual(value, b[key]) then
			return false
		end
	end
	for key in pairs(b) do
		if a[key] == nil then
			return false
		end
	end
	return true
end

--------------------------------------------------------------------------------
-- Value decoding
--------------------------------------------------------------------------------

local function numbers(tagged, count)
	local value = tagged.value
	assert(
		type(value) == "table" and #value == count,
		string.format("%s expects \"value\" to be a list of %d numbers", tagged._type, count)
	)
	for i = 1, count do
		assert(type(value[i]) == "number", string.format("%s value[%d] is not a number", tagged._type, i))
	end
	return value
end

local function keypoints(tagged, minWidth, maxWidth)
	local list = tagged.keypoints
	assert(type(list) == "table" and #list >= 2, tagged._type .. " needs at least 2 keypoints")
	for i, keypoint in ipairs(list) do
		assert(
			type(keypoint) == "table" and #keypoint >= minWidth and #keypoint <= maxWidth,
			string.format("%s keypoint %d must have %d-%d numbers", tagged._type, i, minWidth, maxWidth)
		)
		for j = 1, #keypoint do
			assert(type(keypoint[j]) == "number", string.format("%s keypoint %d has a non-number", tagged._type, i))
		end
	end
	return list
end

local decoders = {}
Importer.decoders = decoders

function decoders.Vector3(t)
	local v = numbers(t, 3)
	return Vector3.new(v[1], v[2], v[3])
end

function decoders.Vector2(t)
	local v = numbers(t, 2)
	return Vector2.new(v[1], v[2])
end

function decoders.Color3(t)
	local v = numbers(t, 3)
	return Color3.new(v[1], v[2], v[3])
end

function decoders.UDim(t)
	local v = numbers(t, 2)
	return UDim.new(v[1], v[2])
end

function decoders.UDim2(t)
	local v = numbers(t, 4)
	return UDim2.new(v[1], v[2], v[3], v[4])
end

function decoders.Rect(t)
	local v = numbers(t, 4)
	return Rect.new(v[1], v[2], v[3], v[4])
end

function decoders.CFrame(t)
	return CFrame.new(table.unpack(numbers(t, 12)))
end

function decoders.NumberRange(t)
	local v = numbers(t, 2)
	return NumberRange.new(v[1], v[2])
end

function decoders.NumberSequence(t)
	local list = {}
	for i, kp in ipairs(keypoints(t, 2, 3)) do
		list[i] = NumberSequenceKeypoint.new(kp[1], kp[2], kp[3] or 0)
	end
	return NumberSequence.new(list)
end

function decoders.ColorSequence(t)
	local list = {}
	for i, kp in ipairs(keypoints(t, 4, 4)) do
		list[i] = ColorSequenceKeypoint.new(kp[1], Color3.new(kp[2], kp[3], kp[4]))
	end
	return ColorSequence.new(list)
end

function decoders.Enum(t)
	assert(type(t.enum) == "string" and type(t.value) == "string", "Enum needs string \"enum\" and \"value\"")
	return Enum[t.enum][t.value]
end

function decoders.BrickColor(t)
	assert(type(t.value) == "string" or type(t.value) == "number", "BrickColor needs a name or number")
	return BrickColor.new(t.value)
end

function decoders.Font(t)
	assert(type(t.family) == "string", "Font needs a string \"family\"")
	return Font.new(t.family, Enum.FontWeight[t.weight or "Regular"], Enum.FontStyle[t.style or "Normal"])
end

function decoders.Content(t)
	assert(type(t.uri) == "string", "Content needs a string \"uri\"")
	return Content.fromUri(t.uri)
end

function decoders.JSONString(t)
	assert(t.value ~= nil, "JSONString needs a \"value\"")
	return Importer.json.encode(t.value)
end

-- Turns a raw JSON value into the Roblox value it describes.
-- Returns value, nil on success or nil, errorMessage on failure.
function Importer.decodeValue(raw)
	local rawType = type(raw)
	if rawType == "string" or rawType == "number" or rawType == "boolean" then
		return raw, nil
	end
	if rawType ~= "table" then
		return nil, "unsupported value of type " .. rawType
	end
	local typeName = raw._type
	if typeName == nil then
		return nil, "untagged object; Roblox values need a \"_type\" (wrap plain JSON in {\"_type\":\"JSONString\"})"
	end
	local decoder = decoders[typeName]
	if not decoder then
		return nil, "unknown _type \"" .. tostring(typeName) .. "\""
	end
	local ok, result = pcall(decoder, raw)
	if not ok then
		return nil, tostring(result)
	end
	return result, nil
end

--------------------------------------------------------------------------------
-- Value comparison
--------------------------------------------------------------------------------

local function valuesEqual(a, b)
	local kind = typeof(a)
	if kind ~= typeof(b) then
		return false
	end
	if kind == "number" then
		return near(a, b)
	elseif kind == "Vector3" then
		return near(a.X, b.X) and near(a.Y, b.Y) and near(a.Z, b.Z)
	elseif kind == "Vector2" then
		return near(a.X, b.X) and near(a.Y, b.Y)
	elseif kind == "Color3" then
		return near(a.R, b.R) and near(a.G, b.G) and near(a.B, b.B)
	elseif kind == "UDim" then
		return near(a.Scale, b.Scale) and near(a.Offset, b.Offset)
	elseif kind == "UDim2" then
		return valuesEqual(a.X, b.X) and valuesEqual(a.Y, b.Y)
	elseif kind == "Rect" then
		return valuesEqual(a.Min, b.Min) and valuesEqual(a.Max, b.Max)
	elseif kind == "CFrame" then
		local ca, cb = { a:GetComponents() }, { b:GetComponents() }
		for i = 1, 12 do
			if not near(ca[i], cb[i]) then
				return false
			end
		end
		return true
	elseif kind == "NumberRange" then
		return near(a.Min, b.Min) and near(a.Max, b.Max)
	elseif kind == "NumberSequence" then
		if #a.Keypoints ~= #b.Keypoints then
			return false
		end
		for i, ka in ipairs(a.Keypoints) do
			local kb = b.Keypoints[i]
			if not (near(ka.Time, kb.Time) and near(ka.Value, kb.Value) and near(ka.Envelope, kb.Envelope)) then
				return false
			end
		end
		return true
	elseif kind == "ColorSequence" then
		if #a.Keypoints ~= #b.Keypoints then
			return false
		end
		for i, ka in ipairs(a.Keypoints) do
			local kb = b.Keypoints[i]
			if not (near(ka.Time, kb.Time) and valuesEqual(ka.Value, kb.Value)) then
				return false
			end
		end
		return true
	elseif kind == "Font" then
		return a.Family == b.Family and a.Weight == b.Weight and a.Style == b.Style
	end
	return a == b
end
Importer.valuesEqual = valuesEqual

-- Does the instance's current value match the raw record value?
local function rawMatches(raw, current)
	if type(raw) == "table" and raw._type == "JSONString" then
		-- Compare by meaning so key order or spacing in the stored text don't count as changes.
		if type(current) ~= "string" then
			return false
		end
		local ok, decoded = pcall(Importer.json.decode, current)
		return ok and deepEqual(decoded, raw.value)
	end
	local expected, err = Importer.decodeValue(raw)
	if err then
		return false
	end
	return valuesEqual(expected, current)
end

--------------------------------------------------------------------------------
-- Parsing and migration
--------------------------------------------------------------------------------

-- Returns record or nil, errorMessage.
function Importer.parseLine(line)
	local ok, result = pcall(Importer.json.decode, line)
	if not ok then
		return nil, "invalid JSON: " .. tostring(result)
	end
	if type(result) ~= "table" or isArray(result) then
		return nil, "line is not a JSON object"
	end
	return result, nil
end

-- Parses JSONL text. Blank lines are skipped; bad lines are reported, not fatal.
-- Returns records, problems where problems = { { line = n, error = "..." }, ... }.
function Importer.parseJsonl(text)
	local records, problems = {}, {}
	local lineNumber = 0
	for line in (text .. "\n"):gmatch("(.-)\r?\n") do
		lineNumber += 1
		if line:match("%S") then
			local record, err = Importer.parseLine(line)
			if record then
				table.insert(records, record)
			else
				table.insert(problems, { line = lineNumber, error = err })
			end
		end
	end
	return records, problems
end

-- Brings a record up to FORMAT_VERSION. Returns record or nil, errorMessage.
function Importer.migrate(record)
	local version = record.formatVersion
	if type(version) ~= "number" then
		return nil, "formatVersion is missing or not a number"
	end
	if version > Importer.FORMAT_VERSION then
		return nil, string.format(
			"formatVersion %d is newer than this importer (%d)",
			version,
			Importer.FORMAT_VERSION
		)
	end
	while version < Importer.FORMAT_VERSION do
		local step = Importer.migrations[version]
		if not step then
			return nil, "no migration from formatVersion " .. version
		end
		record = step(record)
		version += 1
		record.formatVersion = version
	end
	return record, nil
end

--------------------------------------------------------------------------------
-- Validation
--------------------------------------------------------------------------------

-- One unparented instance per class, used to check that classes and properties exist.
local probes = {}

local function probeFor(className)
	local probe = probes[className]
	if probe == nil then
		local ok, instance = pcall(Importer.newInstance, className)
		probe = ok and instance or false
		probes[className] = probe
	end
	return probe or nil
end

-- Returns exists, currentValue for a property on a probe instance.
local function readProperty(probe, name)
	return pcall(function()
		return probe[name]
	end)
end

-- Can a value of this type be assigned to a property currently holding expected?
local function assignable(value, expected)
	if expected == nil then
		return true -- e.g. an unset reference; nothing to compare against
	end
	local have, want = typeof(value), typeof(expected)
	return have == want
		or (want == "Content" and have == "string")
		or (want == "EnumItem" and (have == "string" or have == "number"))
		or (want == "BrickColor" and have == "number")
end

local function validateNode(node, where, errors, warnings)
	if type(node) ~= "table" or isArray(node) then
		table.insert(errors, where .. ": must be an object")
		return
	end
	if type(node.class) ~= "string" or node.class == "" then
		table.insert(errors, where .. ".class: must be a non-empty string")
		return
	end
	if type(node.name) ~= "string" or node.name == "" then
		table.insert(errors, where .. ".name: must be a non-empty string")
	end

	local probe = probeFor(node.class)
	if not probe then
		table.insert(errors, where .. ".class: unknown class \"" .. node.class .. "\"")
	end

	if node.properties ~= nil then
		if type(node.properties) ~= "table" or (next(node.properties) ~= nil and isArray(node.properties)) then
			table.insert(errors, where .. ".properties: must be an object")
		else
			for _, name in ipairs(sortedKeys(node.properties)) do
				local at = where .. ".properties." .. tostring(name)
				if RESERVED_PROPERTIES[name] then
					table.insert(errors, at .. ": reserved; use the node's \"name\"/\"class\" instead")
				else
					local value, err = Importer.decodeValue(node.properties[name])
					if err then
						table.insert(errors, at .. ": " .. err)
					elseif probe then
						local exists, expected = readProperty(probe, name)
						if not exists then
							table.insert(errors, at .. ": " .. node.class .. " has no property \"" .. tostring(name) .. "\"")
						elseif not assignable(value, expected) then
							table.insert(errors, string.format("%s: expected %s, got %s", at, typeof(expected), typeof(value)))
						end
					end
				end
			end
		end
	end

	if node.attributes ~= nil then
		if type(node.attributes) ~= "table" or (next(node.attributes) ~= nil and isArray(node.attributes)) then
			table.insert(errors, where .. ".attributes: must be an object")
		else
			for _, name in ipairs(sortedKeys(node.attributes)) do
				local at = where .. ".attributes." .. tostring(name)
				local value, err = Importer.decodeValue(node.attributes[name])
				if err then
					table.insert(errors, at .. ": " .. err)
				elseif not ATTRIBUTE_TYPES[typeof(value)] then
					table.insert(errors, at .. ": " .. typeof(value) .. " can't be stored as an attribute")
				end
			end
		end
	end

	if node.children ~= nil then
		if not isArray(node.children) then
			table.insert(errors, where .. ".children: must be a list")
		else
			for i, child in ipairs(node.children) do
				validateNode(child, string.format("%s.children[%d]", where, i), errors, warnings)
			end
		end
	end
end

local function promptTextOf(node)
	for _, child in ipairs(node.children or {}) do
		if child.class == "TextLabel" and child.properties and type(child.properties.Text) == "string" then
			return child.properties.Text
		end
	end
	return nil
end

-- Returns ok, errors, warnings. Warnings never block an import.
function Importer.validate(record)
	local errors, warnings = {}, {}
	if type(record) ~= "table" or isArray(record) then
		return false, { "record must be a JSON object" }, warnings
	end

	local migrated, migrateErr = Importer.migrate(record)
	if not migrated then
		return false, { migrateErr }, warnings
	end
	record = migrated

	if type(record.id) ~= "string" or record.id == "" then
		table.insert(errors, "id: must be a non-empty string")
	end

	local path = record.path
	local pathOk = isArray(path) and #path >= 2
	if pathOk then
		for i, segment in ipairs(path) do
			if type(segment) ~= "string" or segment == "" then
				table.insert(errors, string.format("path[%d]: must be a non-empty string", i))
				pathOk = false
			end
		end
	else
		table.insert(errors, "path: must be a list of at least 2 names (attachment, emitter)")
	end

	if record.attachment == nil then
		table.insert(errors, "attachment: missing")
	else
		validateNode(record.attachment, "attachment", errors, warnings)
	end
	if record.emitter == nil then
		table.insert(errors, "emitter: missing")
	else
		validateNode(record.emitter, "emitter", errors, warnings)
	end
	if record.prompt_gui ~= nil then
		validateNode(record.prompt_gui, "prompt_gui", errors, warnings)
	end
	if record.prompt ~= nil and type(record.prompt) ~= "string" then
		table.insert(errors, "prompt: must be a string")
	end
	if #errors > 0 then
		return false, errors, warnings
	end

	-- Cross-field checks
	if pathOk then
		if path[#path] ~= record.emitter.name then
			table.insert(errors, "path: last entry must equal emitter.name")
		end
		if path[#path - 1] ~= record.attachment.name then
			table.insert(errors, "path: second-to-last entry must equal attachment.name")
		end
		if record.id ~= table.concat(path, "/") then
			table.insert(warnings, "id doesn't match path joined by \"/\"")
		end
	end

	if record.emitter.class ~= "ParticleEmitter" then
		table.insert(warnings, "emitter.class is " .. record.emitter.class .. ", not ParticleEmitter")
	end

	local emitCount = record.emitter.attributes and record.emitter.attributes.EmitCount
	if emitCount ~= nil and type(emitCount) ~= "number" then
		table.insert(errors, "emitter.attributes.EmitCount: must be a number")
	elseif record.playback_mode ~= nil and record.playback_mode ~= Importer.playbackMode(record) then
		table.insert(warnings, "playback_mode doesn't match EmitCount")
	end

	if record.prompt_gui and record.prompt then
		local text = promptTextOf(record.prompt_gui)
		if text and text ~= record.prompt then
			table.insert(warnings, "prompt doesn't match the prompt_gui TextLabel text")
		end
	end

	return #errors == 0, errors, warnings
end

--------------------------------------------------------------------------------
-- Playback
--------------------------------------------------------------------------------

-- Accepts a record or an emitter (anything with GetAttribute).
function Importer.emitCount(source)
	local count
	if type(source) == "table" and source.emitter ~= nil then
		count = source.emitter.attributes and source.emitter.attributes.EmitCount
	else
		count = source:GetAttribute("EmitCount")
	end
	return type(count) == "number" and count or 0
end

function Importer.playbackMode(source)
	return Importer.emitCount(source) > 0 and "burst" or "continuous"
end

-- Fires a burst emitter once. Returns the number of particles emitted (0 for continuous emitters).
function Importer.emit(emitter)
	local count = Importer.emitCount(emitter)
	if count > 0 then
		emitter:Emit(count)
	end
	return count
end

--------------------------------------------------------------------------------
-- Building
--------------------------------------------------------------------------------

-- The attachment node with the emitter and prompt as children.
local function recordTree(record)
	local attachment = record.attachment
	local children = {}
	append(children, attachment.children or {})
	table.insert(children, record.emitter)
	if record.prompt_gui then
		table.insert(children, record.prompt_gui)
	elseif type(record.prompt) == "string" then
		table.insert(children, defaultPromptNode(record.prompt))
	end
	return {
		class = attachment.class,
		name = attachment.name,
		properties = attachment.properties,
		attributes = attachment.attributes,
		children = children,
	}
end

local function findChild(parent, name, className)
	for _, child in ipairs(parent:GetChildren()) do
		if child.Name == name and child.ClassName == className then
			return child
		end
	end
	return nil
end

local function treeHasChild(tree, node)
	for _, child in ipairs(tree.children) do
		if child.name == node.name and child.class == node.class then
			return true
		end
	end
	return false
end

-- Combines records that share an attachment into one tree.
local function mergedTree(records, warnings)
	local tree = recordTree(records[1])
	for i = 2, #records do
		local record = records[i]
		if
			not deepEqual(record.attachment.properties or {}, tree.properties or {})
			or not deepEqual(record.attachment.attributes or {}, tree.attributes or {})
		then
			table.insert(warnings, record.id .. ": attachment data differs from " .. records[1].id .. "; using the first")
		end
		for _, child in ipairs(recordTree(record).children) do
			if not treeHasChild(tree, child) then
				table.insert(tree.children, child)
			end
		end
	end
	return tree
end

local function setProperty(instance, name, raw, errors, where)
	local value, err = Importer.decodeValue(raw)
	if err then
		table.insert(errors, where .. "." .. name .. ": " .. err)
		return
	end
	local ok, setErr = pcall(function()
		instance[name] = value
	end)
	if not ok then
		table.insert(errors, where .. "." .. name .. ": " .. tostring(setErr))
	end
end

local function setAttribute(instance, name, raw, errors, where)
	local value, err = Importer.decodeValue(raw)
	if err then
		table.insert(errors, where .. "@" .. name .. ": " .. err)
		return
	end
	local ok, setErr = pcall(instance.SetAttribute, instance, name, value)
	if not ok then
		table.insert(errors, where .. "@" .. name .. ": " .. tostring(setErr))
	end
end

local function buildNode(node, errors, where)
	local ok, instance = pcall(Importer.newInstance, node.class)
	if not ok then
		table.insert(errors, where .. ": can't create " .. tostring(node.class) .. ": " .. tostring(instance))
		return nil
	end
	instance.Name = node.name
	-- Sorted so the result never depends on JSON key order.
	local properties = node.properties or {}
	for _, name in ipairs(sortedKeys(properties)) do
		setProperty(instance, name, properties[name], errors, where)
	end
	local attributes = node.attributes or {}
	for _, name in ipairs(sortedKeys(attributes)) do
		setAttribute(instance, name, attributes[name], errors, where)
	end
	for _, childNode in ipairs(node.children or {}) do
		local child = buildNode(childNode, errors, where .. "/" .. tostring(childNode.name))
		if child then
			child.Parent = instance
		end
	end
	return instance
end

local function buildTree(tree, report, where, options)
	local errors = {}
	local instance = buildNode(tree, errors, where)
	append(report.errors, errors)
	if instance and #errors > 0 and not options.allowPartial then
		instance:Destroy()
		return nil
	end
	return instance
end

-- Builds the attachment, emitter and prompt for one record. The result is NOT parented.
-- Returns instance (or nil), report = { errors = {...}, warnings = {...} }.
-- options.allowPartial keeps the instance even if some properties failed to set.
function Importer.deserialize(record, options)
	options = options or {}
	local report = { errors = {}, warnings = {} }
	local ok, errors, warnings = Importer.validate(record)
	append(report.warnings, warnings)
	if not ok then
		append(report.errors, errors)
		return nil, report
	end
	record = Importer.migrate(record)
	return buildTree(recordTree(record), report, record.id, options), report
end

--------------------------------------------------------------------------------
-- Diffing and updating existing instances
--------------------------------------------------------------------------------

-- Fills changes (actionable) and notes (informational) with the differences between a node and an instance.
local function diffNode(node, instance, changes, notes, where)
	local properties = node.properties or {}
	for _, name in ipairs(sortedKeys(properties)) do
		local raw = properties[name]
		local ok, current = pcall(function()
			return instance[name]
		end)
		if not ok then
			table.insert(notes, { kind = "error", path = where, name = name, message = "can't read property" })
		elseif not rawMatches(raw, current) then
			table.insert(changes, {
				kind = "property", path = where, target = instance, name = name, from = current, raw = raw,
			})
		end
	end

	local attributes = node.attributes or {}
	for _, name in ipairs(sortedKeys(attributes)) do
		local raw = attributes[name]
		local current = instance:GetAttribute(name)
		if not rawMatches(raw, current) then
			table.insert(changes, {
				kind = "attribute", path = where, target = instance, name = name, from = current, raw = raw,
			})
		end
	end
	-- Attributes present in the place but not in the record are reported, never removed.
	for name in pairs(instance:GetAttributes()) do
		if attributes[name] == nil then
			table.insert(notes, { kind = "unlisted_attribute", path = where, name = name })
		end
	end

	for _, childNode in ipairs(node.children or {}) do
		local childPath = where .. "/" .. tostring(childNode.name)
		local existing = findChild(instance, childNode.name, childNode.class)
		if existing then
			diffNode(childNode, existing, changes, notes, childPath)
		else
			table.insert(changes, { kind = "create", path = childPath, target = instance, node = childNode })
		end
	end
end

local function commitChanges(changes, errors)
	for _, change in ipairs(changes) do
		if change.kind == "property" then
			setProperty(change.target, change.name, change.raw, errors, change.path)
		elseif change.kind == "attribute" then
			setAttribute(change.target, change.name, change.raw, errors, change.path)
		elseif change.kind == "create" then
			local childErrors = {}
			local child = buildNode(change.node, childErrors, change.path)
			append(errors, childErrors)
			if child and #childErrors == 0 then
				child.Parent = change.target
			elseif child then
				child:Destroy()
			end
		end
	end
end

-- Wraps a change to the place in one undo step. Changes to instances outside
-- the place (or outside a plugin) just run, so they don't leave empty undo entries.
local function withUndo(label, target, fn)
	local history = game and target:IsDescendantOf(game) and game:GetService("ChangeHistoryService")
	local recording
	if history then
		local ok, id = pcall(history.TryBeginRecording, history, label)
		if ok then
			recording = id
		end
	end
	local ok, err = pcall(fn)
	if recording then
		history:FinishRecording(
			recording,
			ok and Enum.FinishRecordingOperation.Commit or Enum.FinishRecordingOperation.Cancel
		)
	end
	if not ok then
		error(err, 0)
	end
end

-- Compares a record with an existing attachment-level instance.
-- Dry run by default: returns { changes, notes, errors, warnings, committed = false } and touches nothing.
-- With options.commit = true the changes are applied as one undo step. Nothing is ever deleted.
function Importer.apply(record, target, options)
	options = options or {}
	local result = { changes = {}, notes = {}, errors = {}, warnings = {}, committed = false }
	local ok, errors, warnings = Importer.validate(record)
	append(result.warnings, warnings)
	if not ok then
		append(result.errors, errors)
		return result
	end
	record = Importer.migrate(record)

	if target.Name ~= record.attachment.name or target.ClassName ~= record.attachment.class then
		table.insert(result.errors, string.format(
			"target is %s \"%s\" but the record describes %s \"%s\"",
			target.ClassName, target.Name, record.attachment.class, record.attachment.name
		))
		return result
	end

	diffNode(recordTree(record), target, result.changes, result.notes, record.id)

	if options.commit and #result.changes > 0 then
		withUndo("Apply particle record " .. record.id, target, function()
			commitChanges(result.changes, result.errors)
		end)
		result.committed = true
	end
	return result
end

--------------------------------------------------------------------------------
-- Planning and running an import
--------------------------------------------------------------------------------

local function relativeId(root, instance)
	local names = {}
	local current = instance
	while current and current ~= root do
		table.insert(names, 1, current.Name)
		current = current.Parent
	end
	return table.concat(names, "/")
end

local function walkFolders(root, names)
	local current = root
	for _, name in ipairs(names) do
		current = current and current:FindFirstChild(name)
	end
	return current
end

-- Works out what importing these records under root would do, without doing it.
-- Returns plan = {
--   root, actions = { { kind = "create" | "update" | "unchanged", key, folders, tree, changes, notes } },
--   problems = { { id, errors, warnings } },  -- invalid records (skipped) and records with warnings
--   unlisted = { id, ... },                    -- emitters under root that no record mentions (never deleted)
-- }
function Importer.planImport(records, root)
	local plan = { root = root, actions = {}, problems = {}, unlisted = {} }
	local groups, order, seen = {}, {}, {}

	for index, raw in ipairs(records) do
		local ok, errors, warnings = Importer.validate(raw)
		local id = type(raw) == "table" and raw.id or ("#" .. index)
		if ok and seen[id] then
			ok, errors = false, { "duplicate id" }
		end
		if not ok or #warnings > 0 then
			table.insert(plan.problems, { id = id, errors = ok and {} or errors, warnings = warnings })
		end
		if ok then
			local record = Importer.migrate(raw)
			seen[id] = true
			local key = table.concat(record.path, "/", 1, #record.path - 1)
			local group = groups[key]
			if not group then
				local folders = {}
				for i = 1, #record.path - 2 do
					folders[i] = record.path[i]
				end
				group = { key = key, folders = folders, records = {} }
				groups[key] = group
				table.insert(order, key)
			end
			table.insert(group.records, record)
		end
	end

	for _, key in ipairs(order) do
		local group = groups[key]
		local mergeWarnings = {}
		local tree = mergedTree(group.records, mergeWarnings)
		if #mergeWarnings > 0 then
			table.insert(plan.problems, { id = key, errors = {}, warnings = mergeWarnings })
		end
		local parent = walkFolders(root, group.folders)
		local existing = parent and findChild(parent, tree.name, tree.class)
		local action = { key = key, folders = group.folders, tree = tree, changes = {}, notes = {} }
		if existing then
			diffNode(tree, existing, action.changes, action.notes, key)
			action.kind = #action.changes > 0 and "update" or "unchanged"
		else
			action.kind = "create"
		end
		table.insert(plan.actions, action)
	end

	for _, descendant in ipairs(root:GetDescendants()) do
		if descendant:IsA("ParticleEmitter") then
			local id = relativeId(root, descendant)
			if not seen[id] then
				table.insert(plan.unlisted, id)
			end
		end
	end
	table.sort(plan.unlisted)
	return plan
end

-- Counts a plan's actions without running it.
function Importer.summarize(plan)
	local summary = { create = 0, update = 0, unchanged = 0, changes = 0, problems = #plan.problems, unlisted = #plan.unlisted }
	for _, action in ipairs(plan.actions) do
		summary[action.kind] += 1
		summary.changes += #action.changes
	end
	return summary
end

-- Carries out a plan from planImport as a single undo step. This is the only
-- function (besides apply with commit) that changes the place. Missing folders
-- are created; nothing is ever deleted.
-- Returns { created, updated, unchanged, errors }.
function Importer.executePlan(plan, options)
	options = options or {}
	local result = { created = 0, updated = 0, unchanged = 0, errors = {} }
	withUndo("Import particles", plan.root, function()
		for _, action in ipairs(plan.actions) do
			if action.kind == "create" then
				local report = { errors = {}, warnings = {} }
				local instance = buildTree(action.tree, report, action.key, options)
				append(result.errors, report.errors)
				if instance then
					local parent = plan.root
					for _, name in ipairs(action.folders) do
						local folder = parent:FindFirstChild(name)
						if not folder then
							folder = Importer.newInstance("Folder")
							folder.Name = name
							folder.Parent = parent
						end
						parent = folder
					end
					instance.Parent = parent
					result.created += 1
				end
			elseif action.kind == "update" then
				commitChanges(action.changes, result.errors)
				result.updated += 1
			else
				result.unchanged += 1
			end
		end
	end)
	return result
end

return Importer
