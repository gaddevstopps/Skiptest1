
const fs = require('fs');
const csv = require('csv-parser');

const getMailingAddressLine1 = (row) => {
    return row['MAILING ADDRESS LINE 1']
        || row['MAILING STREET ADDRESS']
        || \`\${row['MAIL HOUSE NUMBER'] || ''} \${row['MAIL STREET NAME'] || ''} \${row['MAIL STREET NAME SUFFIX'] || ''} \${row['MAIL UNIT NUMBER'] || ''}\`
            .replace(/\s+/g, ' ')
            .trim();
};

(async () => {
    const results = [];

    fs.createReadStream('input.csv')
        .pipe(csv())
        .on('data', (row) => {
            const address = getMailingAddressLine1(row);
            results.push({ ...row, computedAddress: address });
        })
        .on('end', () => {
            fs.writeFileSync('output.json', JSON.stringify(results, null, 2));
            console.log('CSV processing complete.');
        });
})();
