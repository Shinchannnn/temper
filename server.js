const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const bodyParser = require('body-parser');

const app = express();
app.use(cors());
app.use(bodyParser.json());

// MongoDB Connection
mongoose.connect('mongodb://localhost:27017/pcapAnalyzer', {
    useNewUrlParser: true,
    useUnifiedTopology: true
}).then(() => console.log("MongoDB connected"))
  .catch(err => console.error("MongoDB connection error:", err));

// Template Schema
const TemplateSchema = new mongoose.Schema({
    templateName: { type: String, required: true, unique: true },
    keyValues: { type: Object, default: {} }, // Store key-value pairs as an object
    locked: { type: Boolean, default: false } // Lock the template once saved
});

const Template = mongoose.model('Template', TemplateSchema);

// Save Template with Key-Value Pairs
app.post('/api/save_template', async (req, res) => {
    try {
        const { templateName, keyValuePairs } = req.body;

        // Input Validation
        if (!templateName || !keyValuePairs || Object.keys(keyValuePairs).length === 0) {
            return res.status(400).json({ error: "Template name and key-value pairs are required." });
        }

        // Check if template exists and is locked
        let template = await Template.findOne({ templateName });
        if (template && template.locked) {
            return res.status(403).json({ error: "Configuration is locked and cannot be modified." });
        }

        // Update or create template
        if (template) {
            template.keyValues = keyValuePairs;
            await template.save();
        } else {
            template = new Template({ templateName, keyValues: keyValuePairs });
            await template.save();
        }

        res.status(200).json({ message: "Template saved successfully!" });
    } catch (error) {
        console.error("Error saving template:", error);
        res.status(500).json({ error: "Failed to save configuration." });
    }
});

// Get Validated Key-Value Pairs for a Template
app.get('/get-validated-pairs', async (req, res) => {
    try {
        const { templateName } = req.query;

        // Input Validation
        if (!templateName) {
            return res.status(400).json({ error: "Template name is required." });
        }

        const template = await Template.findOne({ templateName });
        if (!template) {
            return res.status(404).json({ error: "Template not found." });
        }

        res.status(200).json({ templateName: template.templateName, keyValuePairs: template.keyValues });
    } catch (error) {
        console.error("Error fetching validated pairs:", error);
        res.status(500).json({ error: "Failed to retrieve validated key-value pairs." });
    }
});

// Delete a Key-Value Pair from the Template
app.delete('/delete-key-value', async (req, res) => {
    try {
        const { templateName, key } = req.body;

        // Input Validation
        if (!templateName || !key) {
            return res.status(400).json({ error: "Template name and key are required." });
        }

        const template = await Template.findOne({ templateName });
        if (!template) {
            return res.status(404).json({ error: "Template not found." });
        }

        // Use MongoDB $unset to remove the key
        await Template.updateOne({ templateName }, { $unset: { [`keyValues.${key}`]: "" } });

        res.status(200).json({ message: "Key deleted successfully!" });
    } catch (error) {
        console.error("Error deleting key-value pair:", error);
        res.status(500).json({ error: "Failed to delete key-value pair." });
    }
});

app.post('/update-template-values', async (req, res) => {
    try {
        const { templateName, updatedValues } = req.body;

        if (!templateName || Object.keys(updatedValues).length === 0) {
            return res.status(400).json({ error: "Template name and updated values are required." });
        }

        // Delete the old template
        await Template.deleteOne({ templateName });

        // Create a new template with the updated values
        const newTemplate = new Template({
            templateName,
            keyValues: updatedValues
        });

        await newTemplate.save();

        res.status(200).json({ message: "Updated successfully!" });
    } catch (error) {
        console.error("Error updating values:", error);
        res.status(500).json({ error: "Failed to update values." });
    }
});
     

// Lock the Template
app.post('/lock-template', async (req, res) => {
    try {
        const { templateName } = req.body;

        // Input Validation
        if (!templateName) {
            return res.status(400).json({ error: "Template name is required." });
        }

        const template = await Template.findOne({ templateName });
        if (!template) {
            return res.status(404).json({ error: "Template not found." });
        }

        template.locked = true;
        await template.save();

        res.status(200).json({ message: "Template locked successfully." });
    } catch (error) {
        console.error("Error locking template:", error);
        res.status(500).json({ error: "Failed to lock template." });
    }
});

// Get All Saved Templates
app.get('/api/get_templates', async (_req, res) => {
    try {
        const templates = await Template.find({}, { templateName: 1 });
        res.status(200).json(templates);
    } catch (error) {
        console.error("Error retrieving templates:", error);
        res.status(500).json({ error: "Failed to retrieve templates." });
    }
});

// Save Key-Value Pair
app.post('/save-key-value', async (req, res) => {
    try {
        const { templateName, key, value } = req.body;

        // Input Validation
        if (!templateName || !key || !value) {
            return res.status(400).json({ error: "Template name, key, and value are required." });
        }

        const existingTemplate = await Template.findOne({ templateName });

        if (existingTemplate) {
            // Update existing template
            existingTemplate.keyValues[key] = value;
            await existingTemplate.save();
        } else {
            // Create new template
            const newTemplate = new Template({ templateName, keyValues: { [key]: value } });
            await newTemplate.save();
        }

        res.status(201).json({ message: "Key-value pair saved successfully!" });
    } catch (error) {
        console.error("Error saving key-value pair:", error);
        res.status(500).json({ error: "Failed to save key-value pair." });
    }
});
app.delete('/delete-template', async (req, res) => {
    try {
        const { templateName } = req.body;

        if (!templateName) {
            return res.status(400).json({ error: "Template name is required." });
        }

        const deleteResult = await Template.deleteOne({ templateName });

        if (deleteResult.deletedCount === 0) {
            return res.status(404).json({ error: "Template not found." });
        }

        res.status(200).json({ message: "Template deleted successfully!" });
    } catch (error) {
        console.error("Error deleting template:", error);
        res.status(500).json({ error: "Failed to delete template." });
    }
});

app.listen(5000, () => console.log('Server running on port 5000'));


